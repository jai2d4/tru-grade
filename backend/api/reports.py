"""Phase 8 deterministic player-grade API.

Grading output is unified with the athlete roster the same way track
identity is (see backend/api/players.py and the film_grades schema
comment): GradeStore's local JSON file stays the system of record a
running report job reads and writes directly, and every save is mirrored
best-effort into Postgres, with athlete_id resolved from the track's
already-confirmed film_track_assignments row — never guessed.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import best_effort_session, get_db
from app.models import orm
from backend.ai.football_reasoner import FootballReasoningResult
from backend.ai.football_reasoner import FootballReasoner
from backend.ai.provider import create_provider
from backend.api.videos import storage_root
from backend.football.evidence import EvidenceStore
from backend.jobs import store
from backend.football.observations import FootballObservation
from backend.football.truth_report import build_play_observations, five_trait_summary
from backend.grading.models import PositionGrade
from backend.grading.service import GradeStore, calculate_official_grade
from backend.grading.rules_loader import load_position_rules


router = APIRouter(prefix="/api/players", tags=["reports"])
grade_store = GradeStore(storage_root / "grades")
report_jobs_dir = storage_root / "report_jobs"
report_jobs_dir.mkdir(parents=True, exist_ok=True)


class GradeInput(BaseModel):
    observation: FootballObservation
    reasoning: FootballReasoningResult


class CalculateGradeRequest(BaseModel):
    game_id: str = Field(min_length=1)
    position: str = Field(min_length=1)
    items: list[GradeInput]
    # Optional explicit roster link — this endpoint has no track_id to look
    # one up from, unlike the truth-report flow below. Validated only
    # best-effort (see _persist_grade); an unreachable DB never fails the
    # grade calculation itself.
    athlete_id: str | None = None


class TruthReportRequest(BaseModel):
    video_id: str = Field(min_length=1)
    track_id: int = Field(ge=1)
    position: str = Field(min_length=1)


def _report_job_path(player_id: str, video_id: str):
    # Player IDs originate in the UI and must never become filesystem paths.
    job_id = hashlib.sha256(f"{player_id}\0{video_id}".encode("utf-8")).hexdigest()
    return report_jobs_dir / f"{job_id}.json"


async def _persist_grade(
    *, video_id: str, athlete_id: str | None, track_id: int | None, player_id: str, position: str,
    grade: PositionGrade, events: list, demo_traits: dict | None,
) -> None:
    """Best-effort mirror of a GradeStore.save() call into Postgres. Never
    raises: by the time this runs, the local-file save has already
    succeeded, and a DB hiccup here must not lose that result. athlete_id
    is resolved from the track's confirmed film_track_assignments row when
    not passed explicitly — see backend/api/players.py's assign_track."""
    async with best_effort_session() as session:
        if session is None:
            return
        video_uuid: UUID | None = None
        try:
            candidate = UUID(video_id)
            if await session.get(orm.FilmUpload, candidate) is not None:
                video_uuid = candidate
        except ValueError:
            pass

        athlete_uuid: UUID | None = None
        if athlete_id:
            try:
                candidate = UUID(athlete_id)
                if await session.get(orm.Athlete, candidate) is not None:
                    athlete_uuid = candidate
            except ValueError:
                pass
        elif video_uuid is not None and track_id is not None:
            assignment = (await session.execute(
                select(orm.FilmTrackAssignment).where(
                    orm.FilmTrackAssignment.video_id == video_uuid,
                    orm.FilmTrackAssignment.track_id == track_id,
                )
            )).scalar_one_or_none()
            if assignment is not None:
                athlete_uuid = assignment.athlete_id

        session.add(orm.FilmGrade(
            video_id=video_uuid, athlete_id=athlete_uuid, player_id=player_id, position=position,
            game_grade=grade.grade, confidence=grade.confidence,
            position_grade=grade.model_dump(mode="json"),
            events=[event.model_dump(mode="json") for event in events],
            demo_traits=demo_traits,
        ))
        await session.commit()


async def build_truth_report(player_id: str, request: TruthReportRequest,
                             on_progress=None) -> dict:
    """Produce the report, reporting progress through `on_progress`.

    Split out from the endpoint so the worker can run it: the reasoning
    loop makes one LLM call per play and takes minutes, which is far too
    long to hold open inside a web request's background task whose state
    lives on that container's own disk. Returns the terminal payload
    rather than writing it anywhere, so the caller decides where it lands.
    """
    async def report(payload: dict) -> None:
        if on_progress is not None:
            await on_progress(payload)

    try:
        vision_dir = storage_root / "vision" / request.video_id
        tracks = json.loads((vision_dir / "tracks.json").read_text(encoding="utf-8"))
        track = next((item for item in tracks if item["track_id"] == request.track_id), None)
        if track is None:
            raise ValueError("Selected player track was not found.")
        plays = json.loads((storage_root / "football" / request.video_id / "plays.json").read_text(encoding="utf-8"))
        bio_path = vision_dir / "biomechanics.json"
        biomechanics = json.loads(bio_path.read_text(encoding="utf-8")) if bio_path.is_file() else None
        observations = build_play_observations(
            request.video_id, player_id, request.position, track, plays, biomechanics
        )
        allowed_traits = list(load_position_rules(request.position).traits)
        reasoner = FootballReasoner(create_provider())
        pairs = []
        evidence_store = EvidenceStore(storage_root / "evidence")
        for index, observation in enumerate(observations, 1):
            await report({"status": "reasoning",
                          "progress": round(index * 90 / max(len(observations), 1)),
                          "message": f"Reasoning over play {index} of {len(observations)}."})
            reasoning = await reasoner.reason(observation, allowed_traits)
            pairs.append((observation, reasoning))
            for evidence in observation.evidence:
                evidence_store.save(evidence)
        grade, events = calculate_official_grade(request.position, pairs)
        traits = five_trait_summary(grade)
        report = grade_store.save(player_id, request.video_id, grade, events, traits)
        await _persist_grade(
            video_id=request.video_id, athlete_id=None, track_id=request.track_id, player_id=player_id,
            position=request.position, grade=grade, events=events, demo_traits=traits,
        )
        result = {"status": "completed", "progress": 100, "message": "Truth Report completed.",
                  "report": report, "updated_at": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        result = {"status": "failed", "progress": 0, "message": "Truth Report failed.",
                  "error": str(exc), "updated_at": datetime.now(timezone.utc).isoformat()}
    return result


async def _latest_report_job(db: AsyncSession, player_id: str, video_id: str):
    """Newest truth_report job for this player/video pair.

    latest_for_video() alone isn't enough: two players can be graded from
    the same film, and returning another player's report would be a
    serious mix-up rather than a cosmetic one.
    """
    try:
        key = UUID(str(video_id))
    except (ValueError, AttributeError, TypeError):
        return None
    rows = await db.execute(
        select(orm.AnalysisJob)
        .where(orm.AnalysisJob.video_id == key,
               orm.AnalysisJob.job_type == "truth_report",
               orm.AnalysisJob.payload["player_id"].astext == player_id)
        .order_by(orm.AnalysisJob.created_at.desc())
        .limit(1)
    )
    return rows.scalar_one_or_none()


@router.post("/{player_id}/grades", status_code=201)
async def calculate_grade(player_id: str, request: CalculateGradeRequest):
    if any(item.observation.player_id != player_id for item in request.items):
        raise HTTPException(422, "Every observation must belong to the requested player.")
    try:
        grade, events = calculate_official_grade(
            request.position, [(item.observation, item.reasoning) for item in request.items]
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    report = grade_store.save(player_id, request.game_id, grade, events)
    await _persist_grade(
        video_id=request.game_id, athlete_id=request.athlete_id, track_id=None, player_id=player_id,
        position=request.position, grade=grade, events=events, demo_traits=None,
    )
    return report


@router.get("/{player_id}/grades")
async def get_player_grades(player_id: str):
    return {"player_id": player_id, "grades": grade_store.get(player_id)}


_QUEUED_REPORT = {"status": "queued", "progress": 0, "message": "Truth Report queued."}


@router.post("/{player_id}/truth-report", status_code=202)
async def start_truth_report(player_id: str, request: TruthReportRequest,
                             db: AsyncSession = Depends(get_db)):
    """Queues the report for a worker.

    This used to run inline as a web BackgroundTask with its state in a
    file on the web service's own disk. The reasoning loop makes one LLM
    call per play, so it runs for minutes — and a container restart in
    that window left the file reading "reasoning" forever, with nothing
    able to notice or recover it. On the shared queue it gets the same
    heartbeat and stale-recovery the analysis jobs have.
    """
    await store.enqueue(
        db, request.video_id, job_type="truth_report",
        payload={"player_id": player_id, **request.model_dump()},
        message=_QUEUED_REPORT["message"],
    )
    return _QUEUED_REPORT


@router.get("/{player_id}/truth-report/{video_id}")
async def truth_report_status(player_id: str, video_id: str,
                              db: AsyncSession = Depends(get_db)):
    job = await _latest_report_job(db, player_id, video_id)
    if job is None:
        raise HTTPException(404, "Truth Report job not found.")
    if job.result is not None:
        return job.result
    payload = {
        "status": "reasoning" if job.status == "reasoning" else "queued",
        "progress": job.progress or 0,
        "message": job.message or _QUEUED_REPORT["message"],
    }
    # Same honesty as the analysis queue: a queued report with nobody
    # running is not "about to start", and saying so beats a progress bar
    # that will never move.
    if job.status == "queued" and not await store.any_worker_alive(db):
        payload["message"] = (
            "Waiting for an analysis worker. No worker is currently running, so this "
            "Truth Report has not started — it stays queued and begins automatically "
            "once one is available."
        )
        payload["worker_available"] = False
    return payload

"""The analysis worker — the process that actually runs film analysis.

This is what runs on the GPU machine (see docs/WORKER_SETUP_BRIEF.md).
It owns no HTTP surface: it polls the shared Postgres queue, claims a
job, runs the existing pipeline (backend/vision/*, unchanged), and writes
results back. Polling outbound is deliberate — the worker machine sits
behind NAT with no public inbound address, so nothing has to reach *into*
it, and jobs simply wait in the queue whenever it's offline.

Run it with:  python scripts/run_worker.py

The heavy imports (torch, ultralytics, easyocr via backend.vision.*) stay
inside `_run_job` rather than at module scope, so importing this module —
which the web service's test suite does — never drags the CV stack into a
process that has no business loading it.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import socket
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.db import async_session
from backend.jobs import store

logger = logging.getLogger("tru.worker")

POLL_INTERVAL_S = float(os.getenv("WORKER_POLL_INTERVAL_S", "5"))
# Re-checking for dead workers on every single poll would be wasteful;
# once a minute is plenty for a 10-minute staleness window.
STALE_SWEEP_EVERY_S = float(os.getenv("WORKER_STALE_SWEEP_S", "60"))


def worker_identity() -> str:
    """Human-readable owner stamped onto claimed jobs, so it's obvious
    which machine is running what when more than one worker exists."""
    return os.getenv("WORKER_ID") or f"{platform.node() or socket.gethostname()}:{os.getpid()}"


def _analysis_fps() -> float | None:
    value = os.getenv("ANALYSIS_FPS", "native").strip().lower()
    return None if value in {"native", "all", "source", "0"} else float(value)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


async def _run_job(job_id: str, video: dict, storage_root: Path) -> None:
    """Run one job to completion, reporting progress into the queue.

    Mirrors the stage order the previous in-process implementation used,
    including its resume behaviour: a stage whose output is already on
    disk is skipped rather than recomputed, so a job that died midway
    doesn't start over.
    """
    # Imported here, not at module scope — see the module docstring.
    from backend.football.play_segmenter import PlaySegmenter
    from backend.video.frame_extractor import FrameExtractor
    from backend.vision.biomechanics import analyze_biomechanics
    from backend.vision.pipeline import analyze_frames

    video_id = video["video_id"]

    async def report(**fields) -> None:
        async with async_session() as db:
            await store.update(db, job_id, **fields)

    # The pipeline's progress callbacks are synchronous and run inside
    # asyncio.to_thread, so they can't await. Hand them back to the loop.
    loop = asyncio.get_running_loop()

    # Throttled, because each report is a database write. The pipeline
    # calls back once per frame, and native-rate extraction of a 10-minute
    # 60fps clip is ~36,000 frames — which was 36,000 UPDATE+COMMIT round
    # trips, enough to dominate the runtime and outweigh the actual
    # analysis. A watching member cannot perceive more than whole
    # percentage points anyway.
    last_reported = -1

    def progress_cb(value: int) -> None:
        nonlocal last_reported
        percent = int(value)
        if percent == last_reported:
            return
        last_reported = percent
        asyncio.run_coroutine_threadsafe(report(progress=percent), loop)

    def reset_progress() -> None:
        """Each stage counts 0-100 again, so the throttle has to forget the
        previous stage's position or the new one reports nothing."""
        nonlocal last_reported
        last_reported = -1

    await report(status="extracting_frames", progress=1,
                 message="Extracting timestamped tracking frames.")

    frames_root = storage_root / "frames"
    frame_manifest = frames_root / video_id / "frames.json"
    frames = _load_json(frame_manifest) if frame_manifest.with_name("frames.complete").is_file() else None
    if not frames:
        extractor = FrameExtractor(frames_root, _analysis_fps())
        frames = await asyncio.to_thread(
            extractor.extract, video_id, Path(video["file_path"]), progress_cb
        )
        # One small JPEG kept aside so field calibration still works after
        # the full extracted set is reclaimed.
        await asyncio.to_thread(extractor.preserve_keyframe, video_id, frames)
    else:
        await report(message="Resuming from completed frame extraction.", frame_count=len(frames))

    reset_progress()
    await report(status="detecting", progress=0, frame_count=len(frames),
                 message="Detecting players and football objects.")

    vision_dir = storage_root / "vision" / video_id
    detections = _load_json(vision_dir / "detections.json")
    tracks = _load_json(vision_dir / "tracks.json")
    if detections is None or tracks is None:
        detections, tracks = await asyncio.to_thread(
            analyze_frames, video_id, frames, storage_root / "vision", progress_cb
        )
    else:
        await report(message="Resuming from completed detection and tracking.",
                     detection_frames=len(detections), track_count=len(tracks))

    await report(status="tracking", progress=99,
                 message="Finalizing persistent player tracks.")

    biomechanics = None
    if os.getenv("ENABLE_BIOMECHANICS", "false").lower() == "true":
        reset_progress()
        await report(status="biomechanics", progress=0,
                     message="Estimating player pose, football track, and contact geometry.")
        biomechanics = _load_json(vision_dir / "biomechanics.json")
        if biomechanics is None:
            biomechanics = await asyncio.to_thread(
                analyze_biomechanics, video_id, frames, tracks,
                storage_root / "vision", None, None, progress_cb,
            )

    await report(status="segmenting_plays", progress=99, message="Estimating play boundaries.")
    plays = PlaySegmenter().segment(video_id, tracks)
    football_dir = storage_root / "football" / video_id
    football_dir.mkdir(parents=True, exist_ok=True)
    (football_dir / "plays.json").write_text(
        json.dumps([play.model_dump() for play in plays], indent=2), encoding="utf-8"
    )

    async with async_session() as db:
        await store.finish(
            db, job_id, status="completed", progress=100,
            detection_frames=len(detections), track_count=len(tracks),
            biomechanics=bool(biomechanics), error=None,
            message="Detection, tracking, and evidence extraction completed.",
        )


def _identify_sync(payload: dict, storage_root: Path, video_id: str) -> dict:
    """Automatic jersey identification. Synchronous and CPU-bound (OCR and
    image decode), so the caller runs it via asyncio.to_thread.

    Frames are read through LazyFrameStore rather than preloaded: the
    previous in-process version decoded every referenced frame into a dict
    first, which is gigabytes at 1080p.
    """
    from backend.vision.automatic_identity import EasyOCRJerseyReader, identify_player
    from backend.vision.frame_source import LazyFrameStore

    tracks = json.loads((storage_root / "vision" / video_id / "tracks.json").read_text(encoding="utf-8"))
    manifest = json.loads((storage_root / "frames" / video_id / "frames.json").read_text(encoding="utf-8"))

    result = identify_player(
        payload["jersey_number"], payload["school_colors"], tracks,
        LazyFrameStore(manifest), EasyOCRJerseyReader(),
        min_reads=int(os.getenv("JERSEY_ID_MIN_READS", "2")),
        threshold=float(os.getenv("JERSEY_ID_CONFIDENCE", ".62")),
        margin=float(os.getenv("JERSEY_ID_MARGIN", ".12")),
    )
    result.update(
        status_detail="Automatic multi-frame identification completed.",
        player_id=payload.get("player_id"), position=payload.get("position"),
    )
    return result


async def _run_identity_job(job_id: str, job_payload: dict, video_id: str, storage_root: Path) -> None:
    """Identify the requested jersey, then persist the assignment if — and
    only if — the evidence actually selected a track. An uncertain result
    stays uncertain; it is never resolved by guessing."""
    from backend.api.players import AutomaticIdentityRequest, _persist_automatic_assignment

    async with async_session() as db:
        await store.update(db, job_id, status="running", progress=5,
                           message="Reading jersey numbers across tracked frames.")

    result = await asyncio.to_thread(_identify_sync, job_payload, storage_root, video_id)

    if result.get("selected_track_id") is not None:
        await _persist_automatic_assignment(
            video_id, result["selected_track_id"],
            AutomaticIdentityRequest(**{
                k: job_payload.get(k) for k in
                ("jersey_number", "school_colors", "player_id", "position")
            }),
            result["confidence"],
        )

    async with async_session() as db:
        await store.finish(db, job_id, status="completed", progress=100,
                           result=result, message=result.get("status_detail"))

    # Identification is the last stage that reads raw frames, so this is
    # the safe point to reclaim that disk. Calibration keeps working
    # because extraction preserved a keyframe (see preserve_keyframe), and
    # the frames themselves are re-derivable from the source video.
    if os.getenv("DISCARD_FRAMES_AFTER_IDENTITY", "true").lower() == "true":
        from backend.video.frame_extractor import FrameExtractor

        freed = FrameExtractor(storage_root / "frames").discard_frames(video_id)
        if freed:
            logger.info("reclaimed %.1f MB of extracted frames for %s", freed / 1e6, video_id)


async def _run_truth_report_job(job_id: str, job_payload: dict) -> None:
    """Build a Truth Report, streaming its per-play progress into the job
    row so a watching member sees real movement rather than a bar that
    sits still for minutes."""
    from backend.api.reports import TruthReportRequest, build_truth_report

    player_id = job_payload["player_id"]
    request = TruthReportRequest(**{
        key: job_payload[key] for key in ("video_id", "track_id", "position")
    })

    async def on_progress(payload: dict) -> None:
        async with async_session() as db:
            await store.update(
                db, job_id,
                status="reasoning",
                progress=int(payload.get("progress", 0)),
                message=payload.get("message"),
            )

    result = await build_truth_report(player_id, request, on_progress=on_progress)

    async with async_session() as db:
        await store.finish(
            db, job_id,
            status="completed" if result.get("status") == "completed" else "failed",
            progress=int(result.get("progress", 0)),
            message=result.get("message"),
            error=result.get("error"),
            result=result,
        )


async def run_once(storage_root: Path, worker_id: str) -> bool:
    """Claim and run a single job. Returns True if one was processed, so
    the caller can poll again immediately instead of sleeping."""
    from backend.api.videos import video_store

    async with async_session() as db:
        job = await store.claim_next(db, worker_id)
    if job is None:
        return False

    job_id = str(job.job_id)
    video_id = str(job.video_id)
    logger.info("claimed job %s for video %s", job_id, video_id)

    if job.job_type == "truth_report":
        # Reads computed artifacts (tracks/plays/biomechanics), not the
        # film itself, so a missing video file is not a precondition here.
        try:
            await _run_truth_report_job(job_id, job.payload or {})
            logger.info("completed truth_report job %s", job_id)
        except Exception as exc:
            logger.exception("truth_report job %s failed", job_id)
            async with async_session() as db:
                await store.finish(
                    db, job_id, status="failed", error=str(exc),
                    message="Truth Report failed.",
                    result={"status": "failed", "progress": 0,
                            "message": "Truth Report failed.", "error": str(exc)},
                )
        return True

    video = video_store.get(video_id)
    if not video:
        # The queue and the film live on different machines' disks; a job
        # whose file isn't here is a real, reportable condition, not a crash.
        async with async_session() as db:
            await store.finish(
                db, job_id, status="failed",
                error="Video file not found on this worker.",
                message="Analysis failed: the film is not present on the worker machine.",
            )
        logger.error("job %s: video %s missing on this worker", job_id, video_id)
        return True

    try:
        if job.job_type == "identity":
            await _run_identity_job(job_id, job.payload or {}, video_id, storage_root)
        else:
            await _run_job(job_id, video, storage_root)
        logger.info("completed %s job %s", job.job_type, job_id)
    except Exception as exc:  # one bad job must never take the worker down
        logger.exception("job %s failed", job_id)
        failure = {
            "status": "failed",
            "status_detail": "Automatic identification failed.",
            "error": str(exc), "selected_track_id": None, "confidence": 0,
        }
        async with async_session() as db:
            await store.finish(
                db, job_id, status="failed", error=str(exc),
                message=("Automatic identification failed."
                         if job.job_type == "identity"
                         else "Analysis failed and can be resumed."),
                # The identity status endpoint serves `result` verbatim, so a
                # failure has to be expressed there too — not only as a job error.
                **({"result": failure} if job.job_type == "identity" else {}),
            )
    return True


async def main() -> None:
    from backend.api.videos import storage_root

    worker_id = worker_identity()
    logger.info("analysis worker %s starting (polling every %.0fs)", worker_id, POLL_INTERVAL_S)

    last_sweep = 0.0
    while True:
        try:
            now = asyncio.get_running_loop().time()

            # Report liveness every cycle, before anything else can fail.
            # This is what lets the API tell a member "nothing is
            # processing film right now" instead of showing a progress bar
            # that will never move.
            async with async_session() as db:
                await store.record_worker_heartbeat(db, worker_id, os.getenv("TRUGRADE_DEVICE", "auto"))

            if now - last_sweep >= STALE_SWEEP_EVERY_S:
                last_sweep = now
                async with async_session() as db:
                    recovered = await store.requeue_stale(db)
                if recovered:
                    logger.warning("returned %d stalled job(s) to the queue", recovered)
                # Same cadence: finished jobs carry payloads and full result
                # documents, so the table would otherwise grow for the life
                # of the deployment.
                async with async_session() as db:
                    purged = await store.purge_finished_jobs(db)
                if purged:
                    logger.info("purged %d finished job(s) past the retention window", purged)

            if await run_once(storage_root, worker_id):
                continue  # drain the queue before sleeping again
        except Exception:
            # Never exit the loop on an unexpected error — a worker that
            # dies silently is worse than one that retries noisily.
            logger.exception("worker loop error; retrying")
        await asyncio.sleep(POLL_INTERVAL_S)

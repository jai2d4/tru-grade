"""SQLAlchemy ORM models — mirror db/init_schema.sql exactly (Module 5)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY, Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Athlete(Base):
    __tablename__ = "athletes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    grad_year: Mapped[int | None]
    school: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str | None] = mapped_column(String(2))
    position: Mapped[str] = mapped_column(String(4), nullable=False)
    height_in: Mapped[float | None] = mapped_column(Numeric(4, 1))
    weight_lbs: Mapped[int | None]
    forty_s: Mapped[float | None] = mapped_column(Numeric(3, 2))
    shuttle_s: Mapped[float | None] = mapped_column(Numeric(3, 2))
    bench_lbs: Mapped[int | None]
    squat_lbs: Mapped[int | None]
    gpa: Mapped[float | None] = mapped_column(Numeric(3, 2))
    sat: Mapped[int | None]
    act: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")


class FilmUpload(Base):
    __tablename__ = "film_uploads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    athlete_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    gemini_file_id: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(32))
    duration_s: Mapped[float | None] = mapped_column(Numeric(8, 2))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending",
        server_default="pending",
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','uploaded','processing','analyzed','failed')",
            name="film_uploads_status_check",
        ),
    )


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)
    film_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("film_uploads.id", ondelete="SET NULL"))
    position_evaluated: Mapped[str] = mapped_column(String(4), nullable=False)
    projected_tier: Mapped[str | None] = mapped_column(String(16))
    metric_sieve_results: Mapped[dict | None] = mapped_column(JSONB)
    qualifying_tiers: Mapped[list[str] | None] = mapped_column(ARRAY(String(16)))
    is_game_changer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    game_changer_reason: Mapped[str | None] = mapped_column(Text)
    makeup_grades: Mapped[dict | None] = mapped_column(JSONB)
    makeup_grade_down: Mapped[dict | None] = mapped_column(JSONB)
    player_identifier: Mapped[str | None] = mapped_column(Text)
    player_identified: Mapped[bool | None] = mapped_column(Boolean)
    identification_note: Mapped[str | None] = mapped_column(Text)
    film_grades: Mapped[dict | None] = mapped_column(JSONB)
    film_flags: Mapped[list | None] = mapped_column(JSONB)
    film_analysis: Mapped[dict | None] = mapped_column(JSONB)
    model_used: Mapped[str | None] = mapped_column(String(64), default="gemini-3.5-flash")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    athlete: Mapped["Athlete"] = relationship(back_populates="evaluations")


class BoardEntry(Base):
    """Module 7 — Coach Recruitment Board. One row per athlete a coach has
    added to their board; UNIQUE(athlete_id) makes moving between stages an
    upsert rather than creating duplicate cards."""
    __tablename__ = "board_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False, unique=True,
    )
    stage: Mapped[str] = mapped_column(String(16), nullable=False, default="watchlist", server_default="watchlist")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "stage IN ('watchlist','evaluating','offer_board','development','follow_up')",
            name="board_entries_stage_check",
        ),
    )


class TeamNeed(Base):
    """Module 7 — coach-editable priority (1-5 stars) per position."""
    __tablename__ = "team_needs"

    id: Mapped[int] = mapped_column(primary_key=True)
    position: Mapped[str] = mapped_column(String(4), nullable=False, unique=True)
    priority: Mapped[int] = mapped_column(nullable=False, default=3, server_default="3")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("priority BETWEEN 1 AND 5", name="team_needs_priority_check"),
    )


class CoachNote(Base):
    """Module 7 — free-text coach notes on an athlete, newest first."""
    __tablename__ = "coach_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)
    author: Mapped[str | None] = mapped_column(String(128))
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CoachFitScore(Base):
    """Module 7 — coach-set 1-5 fit ratings for an athlete. One row per
    athlete (athlete_id is the primary key), upserted from the Player
    Profile view."""
    __tablename__ = "coach_fit_scores"

    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True,
    )
    scheme_fit: Mapped[int | None]
    culture_fit: Mapped[int | None]
    need_match: Mapped[int | None]
    development: Mapped[int | None]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("scheme_fit IS NULL OR scheme_fit BETWEEN 1 AND 5", name="fit_scheme_check"),
        CheckConstraint("culture_fit IS NULL OR culture_fit BETWEEN 1 AND 5", name="fit_culture_check"),
        CheckConstraint("need_match IS NULL OR need_match BETWEEN 1 AND 5", name="fit_need_check"),
        CheckConstraint("development IS NULL OR development BETWEEN 1 AND 5", name="fit_development_check"),
    )


class FilmTrackAssignment(Base):
    """Links the V2 vision pipeline (backend/api/*) to the same athlete
    roster everything else reads from. video_id is a film_uploads.id — see
    the schema comment in db/init_schema.sql for why that table is reused
    rather than a new one. athlete_id is the real link, set only once a
    coach confirms a tracked player against the roster; automatic
    identification alone never sets it."""
    __tablename__ = "film_track_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("film_uploads.id", ondelete="CASCADE"), nullable=False)
    track_id: Mapped[int] = mapped_column(nullable=False)
    athlete_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("athletes.id", ondelete="SET NULL"))
    player_id: Mapped[str | None] = mapped_column(Text)
    jersey_number: Mapped[str | None] = mapped_column(String(4))
    team: Mapped[str | None] = mapped_column(String(128))
    position: Mapped[str | None] = mapped_column(String(8))
    confidence: Mapped[float | None]
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    source: Mapped[str | None] = mapped_column(String(32))
    candidates: Mapped[list | None] = mapped_column(JSONB, default=list, server_default="[]")
    history: Mapped[list | None] = mapped_column(JSONB, default=list, server_default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("video_id", "track_id", name="film_track_assignments_video_track_key"),)


class FilmGrade(Base):
    """Best-effort durable mirror of backend/grading/service.py's GradeStore
    (the local-JSON file stays the system of record on the report-building
    job's critical path — see the schema comment in db/init_schema.sql).
    athlete_id is set only from an already-confirmed film_track_assignments
    row; this table never resolves a roster link by itself."""
    __tablename__ = "film_grades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    video_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("film_uploads.id", ondelete="CASCADE"))
    athlete_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("athletes.id", ondelete="SET NULL"))
    player_id: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[str] = mapped_column(String(8), nullable=False)
    game_grade: Mapped[float | None]
    confidence: Mapped[float | None]
    position_grade: Mapped[dict] = mapped_column(JSONB, nullable=False)
    events: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    demo_traits: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AthleteShareLink(Base):
    """An unauthenticated, read-only share link for one athlete — see the
    schema comment in db/init_schema.sql for exactly what the public
    endpoint (app/routers/public.py) does and doesn't expose."""
    __tablename__ = "athlete_share_links"

    athlete_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True,
    )
    token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    """Phase 21 — a real account, layered on top of the shared API-key gate.
    A coach's athlete_id stays NULL; an athlete's is set exactly once (see
    app/routers/auth.py for how signup resolves that link). See the schema
    comment in db/init_schema.sql for the full design rationale."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    athlete_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("athletes.id", ondelete="SET NULL"), unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint("role IN ('coach','athlete')", name="users_role_check"),)


class UserSession(Base):
    """A logged-in session — the opaque token is what a request actually
    carries (an httpOnly cookie), never the password. Deleting the row logs
    that session out; it doesn't touch the account."""
    __tablename__ = "user_sessions"

    token: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

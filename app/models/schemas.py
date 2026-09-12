"""Pydantic models — request/response validation for the TRU Scouting Engine."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class Position(str, Enum):
    QB = "QB"
    RB = "RB"
    WR = "WR"
    DB = "DB"
    LB = "LB"
    DE = "DE"
    DL = "DL"
    OL = "OL"
    TE = "TE"


class Tier(str, Enum):
    D1_FBS = "D1_FBS"
    D1_FCS = "D1_FCS"
    D1_FCS_D2 = "D1_FCS_D2"
    D2_D3_NAIA_JUCO = "D2_D3_NAIA_JUCO"
    UNRANKED = "UNRANKED"


class Rank(str, Enum):
    """Qualitative trait/makeup grade, P4-standard — best to worst."""
    GAME_CHANGER = "GAME_CHANGER"
    ALL_CONF = "ALL_CONF"
    WIN_PLUS = "WIN_PLUS"
    WIN = "WIN"
    WIN_MINUS = "WIN_MINUS"
    NGE = "NGE"


# Best-to-worst order, used for averaging and for the grade-down shift.
RANK_ORDER: list[Rank] = [
    Rank.GAME_CHANGER, Rank.ALL_CONF, Rank.WIN_PLUS,
    Rank.WIN, Rank.WIN_MINUS, Rank.NGE,
]


class FilmStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class AthleteCreate(BaseModel):
    first_name: str = Field(..., max_length=64)
    last_name: str = Field(..., max_length=64)
    grad_year: Optional[int] = None
    school: Optional[str] = None
    state: Optional[str] = Field(None, max_length=2)
    position: Position
    height_in: Optional[float] = Field(None, gt=50, lt=90)
    weight_lbs: Optional[int] = Field(None, gt=100, lt=450)
    forty_s: Optional[float] = Field(None, gt=3.8, lt=7.0, description="Laser-timed 40-yd dash")
    shuttle_s: Optional[float] = Field(None, gt=3.0, lt=6.0, description="Laser-timed pro-agility")
    bench_lbs: Optional[int] = None
    squat_lbs: Optional[int] = None
    gpa: Optional[float] = Field(None, ge=0, le=5.0)
    sat: Optional[int] = Field(None, ge=400, le=1600)
    act: Optional[int] = Field(None, ge=1, le=36)


class Athlete(AthleteCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MetricCheck(BaseModel):
    """One row of the metric sieve — a single threshold comparison."""
    metric: str
    athlete_value: Optional[float] = None
    threshold: str
    passed: Optional[bool] = None  # None = data missing, not failed


class SieveResult(BaseModel):
    position: Position
    tier: Tier
    checks: list[MetricCheck]
    hard_metrics_passed: bool
    qualifying_tiers: list[Tier] = []
    is_game_changer: bool = False
    game_changer_reason: Optional[str] = None


class MakeupGrades(BaseModel):
    """Profile & Makeup rubric — graded against the P4 standard."""
    size: Optional[Rank] = None
    athletic_ability: Optional[Rank] = None
    play_history: Optional[Rank] = None
    play_style: Optional[Rank] = None
    character: Optional[Rank] = None


class GradeDown(BaseModel):
    """The overall Makeup grade, shifted down per classification level."""
    overall: Rank
    p4: Rank
    group_of_5: Rank
    fcs: Rank
    d2_d3_naia_juco: Rank


class BoardStage(str, Enum):
    WATCHLIST = "watchlist"
    EVALUATING = "evaluating"
    OFFER_BOARD = "offer_board"
    DEVELOPMENT = "development"
    FOLLOW_UP = "follow_up"


class BoardEntryIn(BaseModel):
    stage: BoardStage
    notes: Optional[str] = None


class BoardEntryOut(BaseModel):
    athlete_id: UUID
    stage: BoardStage
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    position: Optional[str] = None

    class Config:
        from_attributes = True


class TeamNeedIn(BaseModel):
    priority: int = Field(..., ge=1, le=5)


class TeamNeedOut(BaseModel):
    position: Position
    priority: int
    updated_at: datetime

    class Config:
        from_attributes = True


class CoachNoteIn(BaseModel):
    note: str = Field(..., min_length=1)
    author: Optional[str] = None


class CoachNoteOut(BaseModel):
    id: UUID
    athlete_id: UUID
    author: Optional[str] = None
    note: str
    created_at: datetime

    class Config:
        from_attributes = True


class CoachFitScoresIn(BaseModel):
    scheme_fit: Optional[int] = Field(None, ge=1, le=5)
    culture_fit: Optional[int] = Field(None, ge=1, le=5)
    need_match: Optional[int] = Field(None, ge=1, le=5)
    development: Optional[int] = Field(None, ge=1, le=5)


class CoachFitScoresOut(CoachFitScoresIn):
    athlete_id: UUID
    updated_at: datetime

    class Config:
        from_attributes = True


class EvaluationOut(BaseModel):
    id: UUID
    athlete_id: UUID
    film_id: Optional[UUID] = None
    position_evaluated: Position
    projected_tier: Optional[Tier] = None
    qualifying_tiers: list[str] = []
    metric_sieve_results: Optional[dict] = None
    is_game_changer: bool = False
    game_changer_reason: Optional[str] = None
    makeup_grades: Optional[dict] = None
    makeup_grade_down: Optional[dict] = None
    player_identifier: Optional[str] = None
    player_identified: Optional[bool] = None
    identification_note: Optional[str] = None
    film_grades: Optional[dict] = None
    film_flags: Optional[list] = None
    film_analysis: Optional[dict] = None
    model_used: str = "gemini-3.5-flash"
    created_at: datetime

    class Config:
        from_attributes = True


class CoachDashboard(BaseModel):
    total_athletes: int
    total_evaluations: int
    board_counts: dict[str, int]
    team_needs: list[TeamNeedOut]
    recent_evaluations: list[EvaluationOut] = []


class FilmLinkOut(BaseModel):
    """One video where this athlete has a confirmed (or proposed) track
    identity — see backend/api/players.py and the film_track_assignments
    schema comment for what this does and doesn't cover."""
    video_id: UUID
    track_id: int
    filename: str
    jersey_number: Optional[str] = None
    team: Optional[str] = None
    position: Optional[str] = None
    confirmed: bool
    confidence: Optional[float] = None
    source: Optional[str] = None
    updated_at: datetime


class FilmGradeOut(BaseModel):
    """One deterministic V2 grade run linked to this athlete — a best-effort
    mirror of backend/grading/service.py's GradeStore. See the film_grades
    schema comment for what this does and doesn't guarantee (the local
    GradeStore file, not this row, is what a running Truth Report job reads
    and writes directly)."""
    id: UUID
    video_id: Optional[UUID] = None
    position: str
    game_grade: Optional[float] = None
    confidence: Optional[float] = None
    demo_traits: Optional[dict] = None
    created_at: datetime


class ShareLinkOut(BaseModel):
    """The coach/athlete-facing view of a share link — the token itself,
    for building the public URL client-side, plus when it was (re)issued.
    Never includes anything about the athlete; see PublicAthleteOut for
    what the link's own holder sees."""
    token: str
    created_at: datetime


class PublicAthleteOut(BaseModel):
    """Everything (and only what) an unauthenticated visitor with a valid
    share-link token gets to see. Deliberately narrow — see the
    athlete_share_links schema comment for what's excluded and why."""
    first_name: str
    last_name: str
    position: str
    school: Optional[str] = None
    grad_year: Optional[int] = None
    projected_tier: Optional[str] = None
    is_game_changer: bool = False


class UserRole(str, Enum):
    COACH = "coach"
    ATHLETE = "athlete"


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=128)
    role: UserRole
    # Required only when role == ATHLETE — see app/routers/auth.py, which
    # resolves it to an existing or new athletes row. A Pydantic-level
    # required-if-role check would reject the field entirely for coaches, so
    # the actual requirement is enforced in the route instead.
    position: Optional[Position] = None


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class CurrentUser(BaseModel):
    """The authenticated caller — never includes the password hash or the
    raw session token, only what the frontend needs to know who's signed
    in and route them to the right screens."""
    id: UUID
    email: str
    full_name: str
    role: UserRole
    athlete_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True

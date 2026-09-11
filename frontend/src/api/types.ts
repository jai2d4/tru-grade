/**
 * Response contracts for the endpoints this UI already calls.
 *
 * These mirror the current FastAPI responses field-for-field. Phase 16 does not
 * change any endpoint shape, so anything the backend may omit is typed optional
 * rather than assumed present — UNKNOWN and missing values must survive the
 * round trip untouched.
 */

/* ---------- /api/videos ---------- */

export interface UploadedVideo {
  video_id: string;
  filename: string;
  status: string;
}

export interface TrackPosition {
  timestamp_ms: number;
  /** [x1, y1, x2, y2] in source-video pixels. */
  bbox: [number, number, number, number];
}

export interface Track {
  track_id: number;
  frames?: number[];
  positions?: TrackPosition[];
}

export interface TrackAssignment {
  track_id: number;
  player_id?: string | null;
  jersey_number?: string | null;
  team?: string | null;
  position?: string | null;
  candidates?: unknown[];
  confidence?: number;
  confirmed?: boolean;
  history?: unknown[];
}

export interface TracksResponse {
  video_id: string;
  tracks: Track[];
  assignments: Record<string, TrackAssignment>;
}

export interface Play {
  play_id: string;
  snap_time: number;
  confidence: number;
  source: string;
}

export interface PlaysResponse {
  video_id: string;
  plays: Play[];
}

/* ---------- /api/analysis ---------- */

export type AnalysisStatus =
  | "uploaded"
  | "extracting_frames"
  | "detecting"
  | "tracking"
  | "biomechanics"
  | "segmenting_plays"
  | "completed"
  | "failed";

export interface AnalysisJob {
  job_id: string;
  video_id: string;
  status: AnalysisStatus;
  progress: number;
  message?: string;
  frame_count?: number;
  detection_frames?: number;
  track_count?: number;
  biomechanics?: boolean;
  error?: string;
  created_at?: string;
  updated_at?: string;
}

/* ---------- automatic identity ---------- */

export type IdentityStatus = "processing" | "identified" | "uncertain" | "failed";

export interface IdentityResult {
  status: IdentityStatus;
  status_detail?: string;
  selected_track_id: number | null;
  confidence: number;
  error?: string;
}

export interface IdentifyRequest {
  jersey_number: string;
  school_colors: string;
  player_id?: string | null;
  position?: string | null;
}

export interface AssignRequest {
  player_id?: string | null;
  jersey_number: string;
  team?: string | null;
  position?: string | null;
  reason: string;
}

/* ---------- field calibration ---------- */

export interface CalibrationResult {
  status: string;
  confidence: number;
  tracks_calibrated?: number;
}

/* ---------- grades and Truth Report ---------- */

export interface Evidence {
  video_id: string;
  play_id: string;
  timestamp_start: number;
  timestamp_end: number;
  frame_ids?: number[];
  track_id?: number | null;
  player_id?: string | null;
  description: string;
}

export interface TraitScore {
  trait: string;
  score: number;
  confidence: number;
  sample_count: number;
  evidence: Evidence[];
}

export interface PositionGrade {
  position: string;
  grade: number | null;
  confidence: number;
  /** A null trait means the engine had no evidence — render UNKNOWN, never 0. */
  traits: Record<string, TraitScore | null>;
  unknown_traits?: string[];
}

/** One of the five headline traits on the Truth Report. */
export type DemoTrait =
  | { status: "graded"; score: number; confidence: number; official_traits: string[]; evidence: Evidence[] }
  | { status: "unknown"; score: null; confidence: number; official_traits: string[]; evidence: Evidence[] };

export type DemoTraitName =
  | "field_speed"
  | "contact"
  | "play_recognition"
  | "tackling"
  | "versatility";

export interface GradeRecord {
  player_id: string;
  game_id: string;
  position_grade: PositionGrade;
  game_grade: number | null;
  confidence: number;
  events?: unknown[];
  demo_traits?: Partial<Record<DemoTraitName, DemoTrait>>;
}

export interface GradesResponse {
  player_id: string;
  grades: GradeRecord[];
}

export interface TruthReportRequest {
  video_id: string;
  track_id: number;
  position: string;
}

export interface TruthReportJob {
  status: "queued" | "reasoning" | "completed" | "failed";
  progress: number;
  message?: string;
  report?: GradeRecord;
  error?: string;
  updated_at?: string;
}

/* ---------- scout endpoints (Module 1 / Create Profile) ---------- */

export interface PlayerLookupRequest {
  player_name: string;
  school: string | null;
}

export interface LookupSource {
  url: string;
  title?: string;
}

export interface PlayerLookupResponse {
  full_name?: string;
  school?: string;
  school_colors?: string[] | string;
  grad_year?: number | string;
  state?: string;
  jersey_number?: number | string;
  height_in?: number;
  weight_lbs?: number;
  gpa?: number;
  verification_note?: string;
  sources?: LookupSource[];
}

export type MakeupRank = "GAME_CHANGER" | "ALL_CONF" | "WIN_PLUS" | "WIN" | "WIN_MINUS" | "NGE";

export interface FilmAnalysis {
  player_identified?: boolean | null;
  identification_note?: string | null;
  film_grades?: Record<string, MakeupRank | string>;
  flags?: string[];
}

export interface FilmJobCreated {
  job_id: string;
  status: string;
}

export interface FilmJob {
  job_id: string;
  status: "queued" | "processing" | "complete" | "failed";
  message?: string;
  error?: string;
  result?: { analysis?: FilmAnalysis };
}

/* ---------- /api/v1/athletes and Module 7 coach endpoints ----------
 * These mirror app/models/schemas.py field-for-field, same rule as the rest
 * of this file: Phase 16 does not change endpoint shapes, and neither does
 * this addition — it only names and types calls the app didn't make yet.
 * Note this is the legacy nine-position taxonomy (QB/RB/WR/DB/LB/DE/DL/OL/TE),
 * a different list from the 13-position TRUGRADE_POSITIONS used by Film
 * Analysis and Create Profile — do not merge the two.
 */

export const LEGACY_POSITIONS = ["QB", "RB", "WR", "DB", "LB", "DE", "DL", "OL", "TE"] as const;
export type LegacyPosition = (typeof LEGACY_POSITIONS)[number];

export interface Athlete {
  id: string;
  first_name: string;
  last_name: string;
  grad_year?: number | null;
  school?: string | null;
  state?: string | null;
  position: LegacyPosition;
  height_in?: number | null;
  weight_lbs?: number | null;
  forty_s?: number | null;
  shuttle_s?: number | null;
  bench_lbs?: number | null;
  squat_lbs?: number | null;
  gpa?: number | null;
  sat?: number | null;
  act?: number | null;
  created_at: string;
  updated_at: string;
}

export const BOARD_STAGES = ["watchlist", "evaluating", "offer_board", "development", "follow_up"] as const;
export type BoardStage = (typeof BOARD_STAGES)[number];

export const BOARD_STAGE_LABELS: Record<BoardStage, string> = {
  watchlist: "Watchlist",
  evaluating: "Evaluating",
  offer_board: "Offer Board",
  development: "Development",
  follow_up: "Follow-Up",
};

export interface BoardEntry {
  athlete_id: string;
  stage: BoardStage;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  first_name?: string | null;
  last_name?: string | null;
  position?: string | null;
}

export interface TeamNeed {
  position: LegacyPosition;
  priority: number;
  updated_at: string;
}

export interface CoachNote {
  id: string;
  athlete_id: string;
  author?: string | null;
  note: string;
  created_at: string;
}

export interface CoachFitScores {
  scheme_fit?: number | null;
  culture_fit?: number | null;
  need_match?: number | null;
  development?: number | null;
  athlete_id: string;
  updated_at: string;
}

/** One row of app/services/metric_sieve.py's hard-threshold table. */
export interface MetricCheck {
  metric: string;
  athlete_value?: number | null;
  threshold: string;
  /** null = data missing, not failed. */
  passed?: boolean | null;
}

/** app/models/schemas.py SieveResult, as persisted verbatim on the evaluation. */
export interface MetricSieveResults {
  position: LegacyPosition;
  tier: string;
  checks: MetricCheck[];
  hard_metrics_passed: boolean;
  qualifying_tiers?: string[];
  is_game_changer: boolean;
  game_changer_reason?: string | null;
}

/** app/models/schemas.py GradeDown. */
export interface GradeDown {
  overall: MakeupRank;
  p4: MakeupRank;
  group_of_5: MakeupRank;
  fcs: MakeupRank;
  d2_d3_naia_juco: MakeupRank;
}

export interface Evaluation {
  id: string;
  athlete_id: string;
  film_id?: string | null;
  position_evaluated: LegacyPosition;
  projected_tier?: string | null;
  qualifying_tiers: string[];
  metric_sieve_results?: MetricSieveResults | null;
  is_game_changer: boolean;
  game_changer_reason?: string | null;
  makeup_grades?: Record<string, MakeupRank | null> | null;
  makeup_grade_down?: GradeDown | null;
  player_identifier?: string | null;
  player_identified?: boolean | null;
  identification_note?: string | null;
  film_grades?: Record<string, MakeupRank | string> | null;
  film_flags?: string[] | null;
  model_used?: string;
  created_at: string;
}

export interface CoachDashboard {
  total_athletes: number;
  total_evaluations: number;
  board_counts: Record<string, number>;
  team_needs: TeamNeed[];
  recent_evaluations: Evaluation[];
}

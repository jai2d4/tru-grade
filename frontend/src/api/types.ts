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

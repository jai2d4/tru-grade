/**
 * Typed client for the endpoints the Phase 15 page already called.
 *
 * Every request below sends the same method, path and body the inline script
 * sent. Phase 16 changes no endpoint shape; this file only gives those calls
 * names and types.
 */
import { apiBase } from "./base";
import type {
  AnalysisJob,
  AssignRequest,
  CalibrationResult,
  FilmJob,
  FilmJobCreated,
  GradesResponse,
  IdentifyRequest,
  IdentityResult,
  PlayerLookupRequest,
  PlayerLookupResponse,
  PlaysResponse,
  TrackAssignment,
  TracksResponse,
  TruthReportJob,
  TruthReportRequest,
  UploadedVideo,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Baked into the bundle at build time (see Dockerfile) from the same secret
 * the backend checks as API_KEY — see backend/security/identity.py and
 * app/core/auth.py. Undefined in local dev (both sides leave auth off), so
 * this stays a no-op until a real value is built in.
 */
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

/**
 * Mirrors the page's `v2Json` helper: parse JSON, and prefer FastAPI's
 * `detail` string over a bare status code when the request fails.
 *
 * Exported so other endpoint groups (api/coachClient.ts) share the same
 * fetch/error handling instead of re-implementing it.
 */
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (API_KEY) headers.set("X-API-Key", API_KEY);
  // Phase 21's session cookie needs this on every call — harmless for calls
  // that don't touch it, and same-origin (the deployed app) sends cookies by
  // default anyway; this matters for the cross-origin Vite dev server case.
  const response = await fetch(apiBase() + path, { ...init, headers, credentials: "include" });
  const data = await response.json().catch(() => ({}) as unknown);
  if (!response.ok) {
    const detail = (data as { detail?: string }).detail;
    throw new ApiError(detail ?? `HTTP ${response.status}`, response.status);
  }
  return data as T;
}

export function json(body: unknown, method: "POST" | "PUT" = "POST"): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

/* ---------- Film Analysis workspace (Phase 9 / v2) ---------- */

export const videos = {
  upload(file: File): Promise<UploadedVideo> {
    const form = new FormData();
    form.append("file", file);
    return request<UploadedVideo>("/api/videos/upload", { method: "POST", body: form });
  },
  tracks(videoId: string): Promise<TracksResponse> {
    return request<TracksResponse>(`/api/videos/${videoId}/tracks`);
  },
  plays(videoId: string): Promise<PlaysResponse> {
    return request<PlaysResponse>(`/api/videos/${videoId}/plays`);
  },
  startIdentify(videoId: string, body: IdentifyRequest): Promise<IdentityResult> {
    return request<IdentityResult>(`/api/videos/${videoId}/identify`, json(body));
  },
  identifyStatus(videoId: string): Promise<IdentityResult> {
    return request<IdentityResult>(`/api/videos/${videoId}/identify`);
  },
  assignTrack(videoId: string, trackId: number, body: AssignRequest): Promise<TrackAssignment> {
    return request<TrackAssignment>(`/api/videos/${videoId}/tracks/${trackId}/assign`, json(body));
  },
  autoCalibrate(videoId: string): Promise<CalibrationResult> {
    return request<CalibrationResult>(`/api/videos/${videoId}/calibration/auto`, { method: "POST" });
  },
};

export const analysis = {
  start(videoId: string): Promise<AnalysisJob> {
    return request<AnalysisJob>(`/api/analysis/start/${videoId}`, { method: "POST" });
  },
  status(jobId: string): Promise<AnalysisJob> {
    return request<AnalysisJob>(`/api/analysis/status/${jobId}`);
  },
};

export const players = {
  grades(playerId: string): Promise<GradesResponse> {
    return request<GradesResponse>(`/api/players/${encodeURIComponent(playerId)}/grades`);
  },
  startTruthReport(playerId: string, body: TruthReportRequest): Promise<TruthReportJob> {
    return request<TruthReportJob>(
      `/api/players/${encodeURIComponent(playerId)}/truth-report`,
      json(body),
    );
  },
  truthReport(playerId: string, videoId: string): Promise<TruthReportJob> {
    return request<TruthReportJob>(
      `/api/players/${encodeURIComponent(playerId)}/truth-report/${videoId}`,
    );
  },
};

/* ---------- Create Profile / Module 1 scout endpoints ---------- */

const FILM_JOBS = "/api/v1/scout/analyze-film/jobs";

export const scout = {
  playerLookup(body: PlayerLookupRequest): Promise<PlayerLookupResponse> {
    return request<PlayerLookupResponse>("/api/v1/scout/player-lookup", json(body));
  },
  /**
   * The film job accepts multipart with exactly one of `file` or `youtube_url`,
   * plus the optional `player_identifier` string the profile form builds.
   */
  createFilmJob(form: FormData): Promise<FilmJobCreated> {
    return request<FilmJobCreated>(FILM_JOBS, { method: "POST", body: form });
  },
  filmJob(jobId: string): Promise<FilmJob> {
    return request<FilmJob>(`${FILM_JOBS}/${jobId}`);
  },
};

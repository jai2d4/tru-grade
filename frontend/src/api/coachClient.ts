/**
 * Typed client for the legacy /api/v1 athlete roster and Module 7 coach
 * endpoints (board, team needs, coach notes, fit scores, coach dashboard).
 *
 * Same rule as client.ts: these calls send the same method, path, and body
 * the FastAPI routers already accept. No endpoint shapes are invented here.
 */
import { json, request } from "./client";
import type {
  Athlete,
  BoardEntry,
  BoardStage,
  CoachDashboard,
  CoachFitScores,
  CoachNote,
  Evaluation,
  FilmGrade,
  FilmLink,
  LegacyPosition,
} from "./types";

export interface AthleteCreate {
  first_name: string;
  last_name: string;
  position: LegacyPosition;
  grad_year?: number | null;
  school?: string | null;
  state?: string | null;
  height_in?: number | null;
  weight_lbs?: number | null;
  forty_s?: number | null;
  shuttle_s?: number | null;
  gpa?: number | null;
}

export const athletes = {
  list(params?: { position?: LegacyPosition; limit?: number }): Promise<Athlete[]> {
    const search = new URLSearchParams();
    if (params?.position) search.set("position", params.position);
    if (params?.limit) search.set("limit", String(params.limit));
    const qs = search.toString();
    return request<Athlete[]>(`/api/v1/athletes${qs ? `?${qs}` : ""}`);
  },
  get(athleteId: string): Promise<Athlete> {
    return request<Athlete>(`/api/v1/athletes/${athleteId}`);
  },
  create(body: AthleteCreate): Promise<Athlete> {
    return request<Athlete>("/api/v1/athletes", json(body, "POST"));
  },
  filmLinks(athleteId: string): Promise<FilmLink[]> {
    return request<FilmLink[]>(`/api/v1/athletes/${athleteId}/film-links`);
  },
  grades(athleteId: string): Promise<FilmGrade[]> {
    return request<FilmGrade[]>(`/api/v1/athletes/${athleteId}/grades`);
  },
};

export const board = {
  list(stage?: BoardStage): Promise<BoardEntry[]> {
    const qs = stage ? `?stage=${stage}` : "";
    return request<BoardEntry[]>(`/api/v1/board${qs}`);
  },
  upsert(athleteId: string, body: { stage: BoardStage; notes?: string | null }): Promise<BoardEntry> {
    return request<BoardEntry>(`/api/v1/board/${athleteId}`, json(body, "PUT"));
  },
  remove(athleteId: string): Promise<void> {
    return request<void>(`/api/v1/board/${athleteId}`, { method: "DELETE" });
  },
};

export const teamNeeds = {
  list() {
    return request<{ position: LegacyPosition; priority: number; updated_at: string }[]>(
      "/api/v1/team-needs",
    );
  },
  set(position: LegacyPosition, priority: number) {
    return request(`/api/v1/team-needs/${position}`, json({ priority }, "PUT"));
  },
};

export const coachNotes = {
  list(athleteId: string): Promise<CoachNote[]> {
    return request<CoachNote[]>(`/api/v1/athletes/${athleteId}/notes`);
  },
  add(athleteId: string, body: { note: string; author?: string | null }): Promise<CoachNote> {
    return request<CoachNote>(`/api/v1/athletes/${athleteId}/notes`, json(body, "POST"));
  },
};

export const fitScores = {
  get(athleteId: string): Promise<CoachFitScores> {
    return request<CoachFitScores>(`/api/v1/athletes/${athleteId}/fit-scores`);
  },
  set(
    athleteId: string,
    body: {
      scheme_fit?: number | null;
      culture_fit?: number | null;
      need_match?: number | null;
      development?: number | null;
    },
  ): Promise<CoachFitScores> {
    return request<CoachFitScores>(`/api/v1/athletes/${athleteId}/fit-scores`, json(body, "PUT"));
  },
};

export const coachDashboard = {
  get(): Promise<CoachDashboard> {
    return request<CoachDashboard>("/api/v1/coach/dashboard");
  },
};

/** Module 5 — Truth Report history, unchanged by Module 7. */
export const evaluations = {
  list(athleteId: string, limit = 50): Promise<Evaluation[]> {
    return request<Evaluation[]>(`/api/v1/evaluations?athlete_id=${athleteId}&limit=${limit}`);
  },
  get(evaluationId: string): Promise<Evaluation> {
    return request<Evaluation>(`/api/v1/evaluations/${evaluationId}`);
  },
};

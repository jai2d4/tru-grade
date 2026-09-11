import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { athletes, board, coachDashboard, coachNotes, evaluations, fitScores, teamNeeds } from "@/api/coachClient";

/**
 * These assert the exact method, path and body the Module 7 FastAPI routers
 * (app/routers/athletes.py, board.py, coach.py) accept — mirroring
 * apiClient.test.ts's contract for the Phase 9 endpoints.
 */

interface Captured {
  url: string;
  init: RequestInit | undefined;
}

let calls: Captured[] = [];

function mockJson(body: unknown, ok = true, status = 200) {
  return vi.fn((url: string, init?: RequestInit) => {
    calls.push({ url, init });
    return Promise.resolve({
      ok,
      status,
      json: () => Promise.resolve(body),
    } as Response);
  });
}

beforeEach(() => {
  calls = [];
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const base = "http://localhost:3000";

describe("athletes", () => {
  it("lists the roster with no query string by default", async () => {
    vi.stubGlobal("fetch", mockJson([]));
    await athletes.list();
    expect(calls[0]!.url).toBe(`${base}/api/v1/athletes`);
  });

  it("filters by position and limit", async () => {
    vi.stubGlobal("fetch", mockJson([]));
    await athletes.list({ position: "DB", limit: 25 });
    expect(calls[0]!.url).toBe(`${base}/api/v1/athletes?position=DB&limit=25`);
  });

  it("gets one athlete by id", async () => {
    vi.stubGlobal("fetch", mockJson({ id: "a1" }));
    await athletes.get("a1");
    expect(calls[0]!.url).toBe(`${base}/api/v1/athletes/a1`);
  });
});

describe("board", () => {
  it("lists every stage with no filter", async () => {
    vi.stubGlobal("fetch", mockJson([]));
    await board.list();
    expect(calls[0]!.url).toBe(`${base}/api/v1/board`);
  });

  it("filters by stage", async () => {
    vi.stubGlobal("fetch", mockJson([]));
    await board.list("watchlist");
    expect(calls[0]!.url).toBe(`${base}/api/v1/board?stage=watchlist`);
  });

  it("upserts with a PUT carrying stage and notes", async () => {
    vi.stubGlobal("fetch", mockJson({ athlete_id: "a1", stage: "offer_board" }));
    await board.upsert("a1", { stage: "offer_board", notes: "High priority" });
    expect(calls[0]!.url).toBe(`${base}/api/v1/board/a1`);
    expect(calls[0]!.init?.method).toBe("PUT");
    expect(JSON.parse(calls[0]!.init?.body as string)).toEqual({ stage: "offer_board", notes: "High priority" });
  });

  it("removes with a DELETE", async () => {
    vi.stubGlobal("fetch", mockJson({}));
    await board.remove("a1");
    expect(calls[0]!.url).toBe(`${base}/api/v1/board/a1`);
    expect(calls[0]!.init?.method).toBe("DELETE");
  });
});

describe("team needs", () => {
  it("lists needs", async () => {
    vi.stubGlobal("fetch", mockJson([]));
    await teamNeeds.list();
    expect(calls[0]!.url).toBe(`${base}/api/v1/team-needs`);
  });

  it("sets a priority with a PUT", async () => {
    vi.stubGlobal("fetch", mockJson({ position: "QB", priority: 1 }));
    await teamNeeds.set("QB", 1);
    expect(calls[0]!.url).toBe(`${base}/api/v1/team-needs/QB`);
    expect(calls[0]!.init?.method).toBe("PUT");
    expect(JSON.parse(calls[0]!.init?.body as string)).toEqual({ priority: 1 });
  });
});

describe("coach notes", () => {
  it("lists notes for an athlete", async () => {
    vi.stubGlobal("fetch", mockJson([]));
    await coachNotes.list("a1");
    expect(calls[0]!.url).toBe(`${base}/api/v1/athletes/a1/notes`);
  });

  it("adds a note with a POST", async () => {
    vi.stubGlobal("fetch", mockJson({ id: "n1" }));
    await coachNotes.add("a1", { note: "Great tape.", author: "Coach T" });
    expect(calls[0]!.url).toBe(`${base}/api/v1/athletes/a1/notes`);
    expect(calls[0]!.init?.method).toBe("POST");
    expect(JSON.parse(calls[0]!.init?.body as string)).toEqual({ note: "Great tape.", author: "Coach T" });
  });
});

describe("fit scores", () => {
  it("gets fit scores for an athlete", async () => {
    vi.stubGlobal("fetch", mockJson({ athlete_id: "a1" }));
    await fitScores.get("a1");
    expect(calls[0]!.url).toBe(`${base}/api/v1/athletes/a1/fit-scores`);
  });

  it("sets fit scores with a PUT", async () => {
    vi.stubGlobal("fetch", mockJson({ athlete_id: "a1", scheme_fit: 4 }));
    await fitScores.set("a1", { scheme_fit: 4, culture_fit: null });
    expect(calls[0]!.url).toBe(`${base}/api/v1/athletes/a1/fit-scores`);
    expect(calls[0]!.init?.method).toBe("PUT");
    expect(JSON.parse(calls[0]!.init?.body as string)).toEqual({ scheme_fit: 4, culture_fit: null });
  });
});

describe("coach dashboard", () => {
  it("gets the aggregate view", async () => {
    vi.stubGlobal("fetch", mockJson({ total_athletes: 0 }));
    await coachDashboard.get();
    expect(calls[0]!.url).toBe(`${base}/api/v1/coach/dashboard`);
  });
});

describe("evaluations", () => {
  it("lists Truth Report history for an athlete", async () => {
    vi.stubGlobal("fetch", mockJson([]));
    await evaluations.list("a1");
    expect(calls[0]!.url).toBe(`${base}/api/v1/evaluations?athlete_id=a1&limit=50`);
  });

  it("gets one evaluation by id", async () => {
    vi.stubGlobal("fetch", mockJson({ id: "e1" }));
    await evaluations.get("e1");
    expect(calls[0]!.url).toBe(`${base}/api/v1/evaluations/e1`);
  });
});

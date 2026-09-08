import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, analysis, players, scout, videos } from "@/api/client";

/**
 * The migration must not move an endpoint or reshape a payload. These assert
 * the exact method, path and body the Phase 15 inline script sent.
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

/** jsdom serves the suite from localhost:3000, so the API base is the origin. */
const base = "http://localhost:3000";

describe("film analysis endpoints", () => {
  it("uploads a video as multipart under the field name 'file'", async () => {
    vi.stubGlobal("fetch", mockJson({ video_id: "v1", filename: "game.mp4", status: "uploaded" }));
    const file = new File(["x"], "game.mp4", { type: "video/mp4" });

    await videos.upload(file);

    expect(calls).toHaveLength(1);
    expect(calls[0]!.url).toBe(`${base}/api/videos/upload`);
    expect(calls[0]!.init?.method).toBe("POST");
    const body = calls[0]!.init?.body as FormData;
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("file")).toBe(file);
    // The upload must not be sent as JSON — the server reads an UploadFile.
    expect(calls[0]!.init?.headers).toBeUndefined();
  });

  it("starts analysis with a bare POST on the video id", async () => {
    vi.stubGlobal("fetch", mockJson({ job_id: "j1", video_id: "v1", status: "uploaded", progress: 0 }));
    await analysis.start("v1");
    expect(calls[0]!.url).toBe(`${base}/api/analysis/start/v1`);
    expect(calls[0]!.init?.method).toBe("POST");
    expect(calls[0]!.init?.body).toBeUndefined();
  });

  it("polls analysis status by job id", async () => {
    vi.stubGlobal("fetch", mockJson({ job_id: "j1", video_id: "v1", status: "detecting", progress: 40 }));
    await analysis.status("j1");
    expect(calls[0]!.url).toBe(`${base}/api/analysis/status/j1`);
    expect(calls[0]!.init).toBeUndefined();
  });

  it("sends the identity request the automatic identifier expects", async () => {
    vi.stubGlobal("fetch", mockJson({ status: "processing", selected_track_id: null, confidence: 0 }));
    await videos.startIdentify("v1", {
      jersey_number: "12",
      school_colors: "Red, white, black",
      player_id: null,
      position: "LB",
    });

    expect(calls[0]!.url).toBe(`${base}/api/videos/v1/identify`);
    expect(calls[0]!.init?.method).toBe("POST");
    expect(calls[0]!.init?.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(calls[0]!.init?.body as string)).toEqual({
      jersey_number: "12",
      school_colors: "Red, white, black",
      player_id: null,
      position: "LB",
    });
  });

  it("confirms a track with the human-confirmation reason", async () => {
    vi.stubGlobal("fetch", mockJson({ track_id: 3, jersey_number: "12" }));
    await videos.assignTrack("v1", 3, {
      player_id: null,
      jersey_number: "12",
      team: "Red, white, black",
      position: "LB",
      reason: "Human confirmed identity in Film Analysis",
    });

    expect(calls[0]!.url).toBe(`${base}/api/videos/v1/tracks/3/assign`);
    expect(JSON.parse(calls[0]!.init?.body as string).reason).toBe(
      "Human confirmed identity in Film Analysis",
    );
  });

  it("requests automatic calibration with no body", async () => {
    vi.stubGlobal("fetch", mockJson({ status: "calibrated", confidence: 0.8, tracks_calibrated: 4 }));
    await videos.autoCalibrate("v1");
    expect(calls[0]!.url).toBe(`${base}/api/videos/v1/calibration/auto`);
    expect(calls[0]!.init?.method).toBe("POST");
  });
});

describe("report endpoints", () => {
  it("starts a Truth Report with video_id, track_id and position", async () => {
    vi.stubGlobal("fetch", mockJson({ status: "queued", progress: 0 }));
    await players.startTruthReport("jersey-12", { video_id: "v1", track_id: 3, position: "LB" });

    expect(calls[0]!.url).toBe(`${base}/api/players/jersey-12/truth-report`);
    expect(JSON.parse(calls[0]!.init?.body as string)).toEqual({
      video_id: "v1",
      track_id: 3,
      position: "LB",
    });
  });

  it("encodes a player id that would otherwise break the path", async () => {
    vi.stubGlobal("fetch", mockJson({ status: "queued", progress: 0 }));
    await players.truthReport("jordan williams/1", "v1");
    expect(calls[0]!.url).toBe(`${base}/api/players/jordan%20williams%2F1/truth-report/v1`);
  });

  it("reads a player's grades", async () => {
    vi.stubGlobal("fetch", mockJson({ player_id: "p1", grades: [] }));
    await players.grades("p1");
    expect(calls[0]!.url).toBe(`${base}/api/players/p1/grades`);
  });
});

describe("scout endpoints", () => {
  it("posts the player lookup with a null school rather than an empty string", async () => {
    vi.stubGlobal("fetch", mockJson({ full_name: "Jordan Williams" }));
    await scout.playerLookup({ player_name: "Jordan Williams", school: null });

    expect(calls[0]!.url).toBe(`${base}/api/v1/scout/player-lookup`);
    expect(JSON.parse(calls[0]!.init?.body as string)).toEqual({
      player_name: "Jordan Williams",
      school: null,
    });
  });

  it("creates the long-film job on the jobs endpoint", async () => {
    vi.stubGlobal("fetch", mockJson({ job_id: "f1", status: "queued" }));
    const form = new FormData();
    form.append("file", new File(["x"], "game.mp4"));
    form.append("player_identifier", "Jordan Williams, jersey #12");

    await scout.createFilmJob(form);

    expect(calls[0]!.url).toBe(`${base}/api/v1/scout/analyze-film/jobs`);
    expect(calls[0]!.init?.method).toBe("POST");
    expect((calls[0]!.init?.body as FormData).get("player_identifier")).toBe(
      "Jordan Williams, jersey #12",
    );
  });

  it("polls a film job by id", async () => {
    vi.stubGlobal("fetch", mockJson({ job_id: "f1", status: "processing" }));
    await scout.filmJob("f1");
    expect(calls[0]!.url).toBe(`${base}/api/v1/scout/analyze-film/jobs/f1`);
  });
});

describe("error handling", () => {
  it("prefers the FastAPI detail string over the status code", async () => {
    vi.stubGlobal("fetch", mockJson({ detail: "Video not found." }, false, 404));
    await expect(videos.tracks("missing")).rejects.toThrow("Video not found.");
  });

  it("falls back to the status code when there is no detail", async () => {
    vi.stubGlobal("fetch", mockJson({}, false, 500));
    await expect(videos.tracks("v1")).rejects.toThrow("HTTP 500");
  });

  it("reports the status on the error", async () => {
    vi.stubGlobal("fetch", mockJson({ detail: "nope" }, false, 409));
    await expect(videos.tracks("v1")).rejects.toBeInstanceOf(ApiError);
  });
});

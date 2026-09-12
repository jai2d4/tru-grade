import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "@/App";

/**
 * Route-level coverage for the three athlete-facing screens that now read
 * real Module 5 Truth Report history: Athlete Dashboard, AI Film Report,
 * Trait Breakdown.
 */

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

function mockFetchByPath(responses: Record<string, unknown>) {
  return vi.fn((url: string) => {
    const match = Object.entries(responses).find(([path]) => url.includes(path));
    if (!match) {
      return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({ detail: "not mocked" }) } as Response);
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(match[1]) } as Response);
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const ATHLETE = {
  id: "a1",
  first_name: "Jordan",
  last_name: "Williams",
  position: "DB",
  school: "Westview High",
  grad_year: 2027,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const EVALUATION = {
  id: "e1",
  athlete_id: "a1",
  position_evaluated: "DB",
  projected_tier: "D1_FCS",
  qualifying_tiers: ["D1_FCS"],
  metric_sieve_results: {
    position: "DB",
    tier: "D1_FCS",
    checks: [{ metric: "forty_yard_dash", athlete_value: 4.5, threshold: "<= 4.6", passed: true }],
    hard_metrics_passed: true,
    is_game_changer: false,
  },
  is_game_changer: false,
  makeup_grade_down: { overall: "WIN", p4: "WIN_MINUS", group_of_5: "WIN", fcs: "WIN_PLUS", d2_d3_naia_juco: "ALL_CONF" },
  player_identified: true,
  identification_note: "Matched jersey #12, white uniform.",
  film_grades: { Toughness: "WIN" },
  film_flags: [],
  created_at: "2026-02-01T00:00:00Z",
};

describe("Athlete Dashboard route", () => {
  it("shows the honest empty state and touches no network with no athlete selected", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    renderAt("/athlete/dashboard");

    expect(screen.getByRole("note")).toHaveTextContent(/no athlete selected/i);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("renders real Truth Report counts for the selected athlete", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchByPath({
        "/api/v1/evaluations": [EVALUATION],
        "/api/v1/athletes/a1/film-links": [],
        "/api/v1/athletes/a1/grades": [],
        "/api/v1/athletes/a1": ATHLETE,
      }),
    );

    renderAt("/athlete/dashboard?athleteId=a1");

    expect(await screen.findByRole("heading", { name: "Jordan Williams" })).toBeInTheDocument();
    const reportsTile = screen.getByRole("heading", { name: /truth reports on file/i }).closest(".card");
    expect(within(reportsTile as HTMLElement).getByText("1")).toBeInTheDocument();
  });

  it("shows real linked film from the V2 pipeline", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchByPath({
        "/api/v1/evaluations": [EVALUATION],
        "/api/v1/athletes/a1/film-links": [
          {
            video_id: "v1", track_id: 1, filename: "scrimmage.mp4", jersey_number: "12",
            confirmed: true, updated_at: "2026-02-01T00:00:00Z",
          },
        ],
        "/api/v1/athletes/a1/grades": [],
        "/api/v1/athletes/a1": ATHLETE,
      }),
    );

    renderAt("/athlete/dashboard?athleteId=a1");

    expect(await screen.findByText("scrimmage.mp4")).toBeInTheDocument();
  });

  it("shows a real V2 deterministic grade, linked the same way as film", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchByPath({
        "/api/v1/evaluations": [EVALUATION],
        "/api/v1/athletes/a1/film-links": [],
        "/api/v1/athletes/a1/grades": [
          {
            id: "g1", video_id: "v1", position: "DB", game_grade: 62, confidence: 0.8,
            created_at: "2026-02-01T00:00:00Z",
          },
        ],
        "/api/v1/athletes/a1": ATHLETE,
      }),
    );

    renderAt("/athlete/dashboard?athleteId=a1");

    expect(await screen.findByText(/62/)).toBeInTheDocument();
    expect(screen.getByText(/confidence 80%/i)).toBeInTheDocument();
  });
});

describe("AI Film Report route", () => {
  it("renders real film grades from the most recent report", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchByPath({
        "/api/v1/evaluations": [EVALUATION],
        "/api/v1/athletes/a1": ATHLETE,
      }),
    );

    renderAt("/athlete/film-report?athleteId=a1");

    expect(await screen.findByText("Toughness")).toBeInTheDocument();
    expect(screen.getByText("Win")).toBeInTheDocument();
    expect(screen.getByText(/matched jersey #12/i)).toBeInTheDocument();
  });
});

describe("Trait Breakdown route", () => {
  it("renders real hard metrics and the Profile & Makeup grade-down", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchByPath({
        "/api/v1/evaluations": [EVALUATION],
        "/api/v1/athletes/a1": ATHLETE,
      }),
    );

    renderAt("/athlete/traits?athleteId=a1&evaluationId=e1");

    expect(await screen.findByText("forty yard dash")).toBeInTheDocument();
    expect(screen.getByText("PASS")).toBeInTheDocument();
    const p4Row = screen.getByText("Power 4").closest(".row-item");
    expect(within(p4Row as HTMLElement).getByText("Win-")).toBeInTheDocument();
  });
});

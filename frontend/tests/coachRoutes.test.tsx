import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "@/App";

/**
 * Route-level coverage for the three Module 7 screens that now have a real
 * backend behind them: Coach Dashboard, Recruitment Board, Player Profile.
 */

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

/** Routes each mocked response by matching a substring of the request URL. */
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

describe("Coach Dashboard route", () => {
  it("renders real counts from the dashboard endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchByPath({
        "/api/v1/coach/dashboard": {
          total_athletes: 12,
          total_evaluations: 7,
          board_counts: { watchlist: 2, evaluating: 1, offer_board: 3, development: 0, follow_up: 0 },
          team_needs: [{ position: "QB", priority: 1, updated_at: "2026-01-01T00:00:00Z" }],
          recent_evaluations: [],
        },
      }),
    );

    renderAt("/coach/dashboard");

    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.queryByText("COMING SOON")).not.toBeInTheDocument();
  });

  it("shows an honest error instead of the backend's data when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("network down"))));

    renderAt("/coach/dashboard");

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not reach/i);
  });
});

describe("Recruitment Board route", () => {
  it("groups real board entries into their stage column", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchByPath({
        "/api/v1/board": [
          {
            athlete_id: "a1",
            stage: "watchlist",
            notes: null,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
            first_name: "Jordan",
            last_name: "Williams",
            position: "DB",
          },
        ],
      }),
    );

    renderAt("/coach/board");

    expect(await screen.findByText("Jordan Williams")).toBeInTheDocument();
    const watchlistColumn = screen.getByRole("heading", { level: 3, name: /watchlist/i }).closest(".card");
    expect(watchlistColumn).not.toBeNull();
    expect(within(watchlistColumn as HTMLElement).getByText("1 athlete")).toBeInTheDocument();
  });
});

describe("Player Profile route", () => {
  it("prompts to pick an athlete from the board when none is selected, and touches no network", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    renderAt("/coach/player-profile");

    const note = screen.getByRole("note");
    expect(within(note).getByText(/no athlete selected/i)).toBeInTheDocument();
    expect(within(note).getByRole("link", { name: /recruitment board/i })).toHaveAttribute("href", "/coach/board");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("loads the selected athlete's real name, notes, and fit scores", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchByPath({
        "/api/v1/athletes/a1/notes": [
          { id: "n1", athlete_id: "a1", author: "Coach T", note: "Great tape.", created_at: "2026-01-01T00:00:00Z" },
        ],
        "/api/v1/athletes/a1/fit-scores": {
          athlete_id: "a1",
          scheme_fit: null,
          culture_fit: null,
          need_match: null,
          development: null,
          updated_at: "2026-01-01T00:00:00Z",
        },
        "/api/v1/athletes/a1": {
          id: "a1",
          first_name: "Jordan",
          last_name: "Williams",
          position: "DB",
          school: "Westview High",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      }),
    );

    renderAt("/coach/player-profile?athleteId=a1");

    expect(await screen.findByRole("heading", { name: "Jordan Williams" })).toBeInTheDocument();
    expect(await screen.findByText("Great tape.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText(/not yet rated/i).length).toBeGreaterThan(0));
  });
});

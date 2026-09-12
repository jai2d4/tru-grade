import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { App } from "@/App";

/**
 * Public Rating — the coach/athlete-facing share-link manager
 * (/athlete/public-rating) and the anonymous landing page it points at
 * (/public/:token, rendered outside AppShell — see App.tsx).
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

describe("Public Rating route", () => {
  it("prompts to pick an athlete when none is selected, and touches no network", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    renderAt("/athlete/public-rating");

    expect(screen.getByRole("note")).toHaveTextContent(/no athlete selected/i);
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(screen.queryByText("COMING SOON")).not.toBeInTheDocument();
  });

  it("shows no share link yet, then generates one and displays the real public URL", async () => {
    let issued = false;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (url.includes("/api/v1/evaluations")) {
          return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) } as Response);
        }
        if (url.endsWith("/api/v1/athletes/a1")) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () =>
              Promise.resolve({
                id: "a1", first_name: "Jordan", last_name: "Williams", position: "DB",
                created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
              }),
          } as Response);
        }
        if (url.endsWith("/api/v1/athletes/a1/share-link") && init?.method === "POST") {
          issued = true;
          return Promise.resolve({
            ok: true,
            status: 201,
            json: () => Promise.resolve({ token: "real-token-123", created_at: "2026-03-01T00:00:00Z" }),
          } as Response);
        }
        if (url.endsWith("/api/v1/athletes/a1/share-link")) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve(issued ? { token: "real-token-123", created_at: "2026-03-01T00:00:00Z" } : null),
          } as Response);
        }
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) } as Response);
      }),
    );

    renderAt("/athlete/public-rating?athleteId=a1");

    expect(await screen.findByRole("heading", { name: "Jordan Williams" })).toBeInTheDocument();
    expect(screen.getByText(/no share link has been generated yet/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /generate share link/i }));

    const input = await screen.findByLabelText("Public link");
    expect(input).toHaveValue("http://localhost:3000/public/real-token-123");
    expect(screen.getByRole("button", { name: /revoke/i })).toBeInTheDocument();
  });

  it("revokes an existing share link", async () => {
    let revoked = false;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (url.includes("/api/v1/evaluations")) {
          return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) } as Response);
        }
        if (url.endsWith("/api/v1/athletes/a1")) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () =>
              Promise.resolve({
                id: "a1", first_name: "Jordan", last_name: "Williams", position: "DB",
                created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
              }),
          } as Response);
        }
        if (url.endsWith("/api/v1/athletes/a1/share-link") && init?.method === "DELETE") {
          revoked = true;
          return Promise.resolve({ ok: true, status: 204, json: () => Promise.resolve({}) } as Response);
        }
        if (url.endsWith("/api/v1/athletes/a1/share-link")) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve(revoked ? null : { token: "real-token-123", created_at: "2026-03-01T00:00:00Z" }),
          } as Response);
        }
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) } as Response);
      }),
    );

    renderAt("/athlete/public-rating?athleteId=a1");

    await screen.findByLabelText("Public link");
    await userEvent.click(screen.getByRole("button", { name: /revoke/i }));

    expect(await screen.findByText(/no share link has been generated yet/i)).toBeInTheDocument();
  });
});

describe("Public athlete landing page", () => {
  it("shows only the basics and verified tier — outside the app shell", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchByPath({
        "/api/v1/public/athletes/real-token-123": {
          first_name: "Jordan",
          last_name: "Williams",
          position: "DB",
          school: "Westview High",
          grad_year: 2027,
          projected_tier: "D1_FCS",
          is_game_changer: false,
        },
      }),
    );

    renderAt("/public/real-token-123");

    expect(await screen.findByRole("heading", { name: "Jordan Williams" })).toBeInTheDocument();
    expect(screen.getByText(/Westview High/)).toBeInTheDocument();
    expect(screen.getByText(/Class of 2027/)).toBeInTheDocument();
    // No sidebar/nav chrome — this route is rendered outside AppShell.
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("shows an honest error for an invalid or revoked token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({ detail: "not found" }) } as Response),
      ),
    );

    renderAt("/public/not-a-real-token");

    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid or has been revoked/i);
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { App } from "@/App";

/**
 * Phase 21 — real accounts: login, signup, account settings, and the
 * sidebar's signed-in indicator. All backed by app/routers/auth.py and a
 * real httpOnly session cookie (mocked here via /api/v1/auth/me).
 */

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

/**
 * Every test starts "logged out" (a 401 from /me) unless overridden. A
 * response key is either a bare path ("/api/v1/foo", matched against any
 * method) or "METHOD /api/v1/foo" (matched only against that method).
 */
function mockFetch(responses: Record<string, { status: number; body: unknown }>) {
  return vi.fn((url: string, init?: RequestInit) => {
    const method = (init?.method ?? "GET").toUpperCase();
    const match = Object.entries(responses).find(([key]) => {
      const [maybeMethod, ...rest] = key.split(" ");
      if (rest.length === 0) return url.includes(key);
      return method === maybeMethod && url.includes(rest.join(" "));
    });
    if (!match) {
      if (url.includes("/api/v1/auth/me")) {
        return Promise.resolve({ ok: false, status: 401, json: () => Promise.resolve({ detail: "Not signed in." }) } as Response);
      }
      return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({ detail: "not mocked" }) } as Response);
    }
    const [, { status, body }] = match;
    return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) } as Response);
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Login route", () => {
  it("logs in a coach and redirects to the coach dashboard", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "POST /api/v1/auth/login": {
          status: 200,
          body: {
            id: "u1", email: "coach@example.com", full_name: "Coach T", role: "coach",
            athlete_id: null, created_at: "2026-01-01T00:00:00Z",
          },
        },
        "/api/v1/coach/dashboard": {
          status: 200,
          body: { total_athletes: 0, total_evaluations: 0, board_counts: {}, team_needs: [], recent_evaluations: [] },
        },
      }),
    );

    renderAt("/login");
    await userEvent.type(screen.getByLabelText("Email"), "coach@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "hunter22");
    await userEvent.click(screen.getByRole("button", { name: "Login" }));

    expect(await screen.findByText("Coach T")).toBeInTheDocument(); // sidebar footer
  });

  it("shows an honest error on wrong credentials, without navigating anywhere", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "POST /api/v1/auth/login": { status: 401, body: { detail: "Invalid email or password." } },
      }),
    );

    renderAt("/login");
    await userEvent.type(screen.getByLabelText("Email"), "coach@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Login" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
  });
});

describe("Create Account route", () => {
  it("signs up a coach and redirects to the coach dashboard", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "POST /api/v1/auth/signup": {
          status: 201,
          body: {
            id: "u2", email: "newcoach@example.com", full_name: "New Coach", role: "coach",
            athlete_id: null, created_at: "2026-01-01T00:00:00Z",
          },
        },
        "/api/v1/coach/dashboard": {
          status: 200,
          body: { total_athletes: 0, total_evaluations: 0, board_counts: {}, team_needs: [], recent_evaluations: [] },
        },
      }),
    );

    renderAt("/create-account");
    await userEvent.click(screen.getByRole("button", { name: /coach — evaluate/i }));
    await userEvent.type(screen.getByLabelText("Full Name"), "New Coach");
    await userEvent.type(screen.getByLabelText("Email Address"), "newcoach@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "hunter22x");
    await userEvent.type(screen.getByLabelText("Confirm Password"), "hunter22x");
    await userEvent.click(screen.getByRole("button", { name: /continue/i }));

    expect(await screen.findByText("New Coach")).toBeInTheDocument(); // sidebar footer
  });

  it("requires a position when signing up as an athlete", async () => {
    vi.stubGlobal("fetch", mockFetch({}));

    renderAt("/create-account");
    await userEvent.click(screen.getByRole("button", { name: /athlete — track/i }));
    expect(screen.getByLabelText("Position")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Full Name"), "Some Athlete");
    await userEvent.type(screen.getByLabelText("Email Address"), "athlete@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "hunter22x");
    await userEvent.type(screen.getByLabelText("Confirm Password"), "hunter22x");
    await userEvent.click(screen.getByRole("button", { name: /continue/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/choose a position/i);
  });

  it("rejects mismatched passwords before ever touching the network", async () => {
    const fetchSpy = mockFetch({});
    vi.stubGlobal("fetch", fetchSpy);

    renderAt("/create-account");
    await userEvent.click(screen.getByRole("button", { name: /coach — evaluate/i }));
    await userEvent.type(screen.getByLabelText("Full Name"), "Mismatch Test");
    await userEvent.type(screen.getByLabelText("Email Address"), "mismatch@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "hunter22x");
    await userEvent.type(screen.getByLabelText("Confirm Password"), "different");
    await userEvent.click(screen.getByRole("button", { name: /continue/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/do not match/i);
    expect(fetchSpy.mock.calls.some((call) => String(call[0]).includes("/api/v1/auth/signup"))).toBe(false);
  });
});

describe("Account Settings route", () => {
  it("prompts to log in when no one is signed in", async () => {
    vi.stubGlobal("fetch", mockFetch({}));

    renderAt("/account");

    expect(await screen.findByRole("note")).toHaveTextContent(/not signed in/i);
  });

  it("shows the real signed-in coach profile and logs out", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "GET /api/v1/auth/me": {
          status: 200,
          body: {
            id: "u1", email: "coach@example.com", full_name: "Coach T", role: "coach",
            athlete_id: null, created_at: "2026-01-01T00:00:00Z",
          },
        },
        "POST /api/v1/auth/logout": { status: 204, body: null },
      }),
    );

    renderAt("/account");

    expect(await screen.findByText("coach@example.com")).toBeInTheDocument();
    expect(screen.getAllByText("Coach T").length).toBeGreaterThan(0); // profile card + sidebar footer

    const logoutButtons = screen.getAllByRole("button", { name: /log out/i });
    await userEvent.click(logoutButtons[0]!);
    // Logging out sends the browser to the login screen.
    expect(await screen.findByLabelText("Email")).toBeInTheDocument();
  });

  it("shows the linked athlete's roster details for a signed-in athlete", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "GET /api/v1/auth/me": {
          status: 200,
          body: {
            id: "u3", email: "athlete@example.com", full_name: "Jordan Williams", role: "athlete",
            athlete_id: "a1", created_at: "2026-01-01T00:00:00Z",
          },
        },
        "/api/v1/athletes/a1": {
          status: 200,
          body: {
            id: "a1", first_name: "Jordan", last_name: "Williams", position: "DB", school: "Westview High",
            created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
          },
        },
      }),
    );

    renderAt("/account");

    expect(await screen.findByText("Westview High")).toBeInTheDocument();
    expect(screen.getByText("DB")).toBeInTheDocument();
  });
});

describe("Forgot Password route", () => {
  it("requests a reset link and shows the dev link when email isn't configured", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "POST /api/v1/auth/forgot-password": {
          status: 202,
          body: {
            detail: "If an account with that email exists, a reset link has been sent.",
            dev_reset_url: "http://localhost:3000/reset-password?token=real-dev-token-123",
          },
        },
      }),
    );

    renderAt("/forgot-password");
    await userEvent.type(screen.getByLabelText("Email"), "coach@example.com");
    await userEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    expect(await screen.findByText(/if an account with that email exists/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/local\/dev link/i)).toHaveValue(
      "http://localhost:3000/reset-password?token=real-dev-token-123",
    );
  });

  it("shows an honest message when email delivery isn't configured in production", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "POST /api/v1/auth/forgot-password": {
          status: 503,
          body: { detail: "Password reset isn't available yet — email delivery isn't configured." },
        },
      }),
    );

    renderAt("/forgot-password");
    await userEvent.type(screen.getByLabelText("Email"), "coach@example.com");
    await userEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/isn't available yet/i);
  });
});

describe("Reset Password route", () => {
  it("prompts for a token when none is in the URL, and touches no network", async () => {
    const fetchSpy = mockFetch({});
    vi.stubGlobal("fetch", fetchSpy);

    renderAt("/reset-password");

    expect(await screen.findByRole("alert")).toHaveTextContent(/missing reset token/i);
    const calledForgotOrReset = fetchSpy.mock.calls.some(
      (call) => String(call[0]).includes("/auth/forgot-password") || String(call[0]).includes("/auth/reset-password"),
    );
    expect(calledForgotOrReset).toBe(false);
  });

  it("rejects mismatched passwords before touching the network", async () => {
    const fetchSpy = mockFetch({});
    vi.stubGlobal("fetch", fetchSpy);

    renderAt("/reset-password?token=real-token-123");
    await userEvent.type(screen.getByLabelText("New Password"), "brand-new-pw");
    await userEvent.type(screen.getByLabelText("Confirm Password"), "different-pw");
    await userEvent.click(screen.getByRole("button", { name: /reset password/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/do not match/i);
    expect(fetchSpy.mock.calls.some((call) => String(call[0]).includes("/auth/reset-password"))).toBe(false);
  });

  it("sets the new password with a real token and logs straight in", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "POST /api/v1/auth/reset-password": {
          status: 200,
          body: {
            id: "u1", email: "coach@example.com", full_name: "Coach T", role: "coach",
            athlete_id: null, created_at: "2026-01-01T00:00:00Z",
          },
        },
        "/api/v1/coach/dashboard": {
          status: 200,
          body: { total_athletes: 0, total_evaluations: 0, board_counts: {}, team_needs: [], recent_evaluations: [] },
        },
      }),
    );

    renderAt("/reset-password?token=real-token-123");
    await userEvent.type(screen.getByLabelText("New Password"), "brand-new-pw");
    await userEvent.type(screen.getByLabelText("Confirm Password"), "brand-new-pw");
    await userEvent.click(screen.getByRole("button", { name: /reset password/i }));

    // Landed on the coach dashboard, signed in as the real returned user.
    expect(await screen.findByText("Coach T")).toBeInTheDocument(); // sidebar footer
  });

  it("shows an honest error and a way to request a new link for an invalid token", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "POST /api/v1/auth/reset-password": {
          status: 400,
          body: { detail: "This reset link is invalid or has expired." },
        },
      }),
    );

    renderAt("/reset-password?token=stale-token");
    await userEvent.type(screen.getByLabelText("New Password"), "brand-new-pw");
    await userEvent.type(screen.getByLabelText("Confirm Password"), "brand-new-pw");
    await userEvent.click(screen.getByRole("button", { name: /reset password/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/invalid or has expired/i);
    expect(within(alert).getByRole("link", { name: /request a new link/i })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
  });
});

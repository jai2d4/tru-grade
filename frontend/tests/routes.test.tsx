import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { App } from "@/App";

/**
 * Route-level coverage for the two working screens.
 *
 * Entering the app at a path is what a browser reload does, so an assertion
 * that a deep entry renders the right view is the reload test.
 */

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  // No test in this file should reach the network.
  vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("network disabled in tests"))));
});

describe("Create Profile route", () => {
  it("is the index route", () => {
    renderAt("/");
    expect(screen.getByRole("heading", { level: 1, name: /CREATE\s+PROFILE/i })).toBeInTheDocument();
  });

  it("renders the profile form fields the film job identifies a player with", () => {
    renderAt("/");
    expect(screen.getByLabelText("Athlete Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Player Number to Track")).toBeInTheDocument();
    expect(screen.getByLabelText("School Colors")).toBeInTheDocument();
    expect(screen.getByLabelText("Height (in)")).toBeInTheDocument();
    expect(screen.getByLabelText("Weight (lbs)")).toBeInTheDocument();
    expect(screen.getByLabelText("GPA")).toBeInTheDocument();
  });

  it("shows the Truth Report placeholder until a report is generated", () => {
    renderAt("/");
    expect(screen.getByText("AI TRUTH REPORT")).toBeInTheDocument();
    expect(
      screen.getByText(/Upload game film to generate the AI Truth Report/i),
    ).toBeInTheDocument();
  });

  it("keeps the report anchor addressable so /#report survives a reload", () => {
    const { container } = renderAt("/#report");
    expect(screen.getByRole("heading", { level: 1, name: /CREATE\s+PROFILE/i })).toBeInTheDocument();
    expect(container.querySelector("#report")).not.toBeNull();
  });
});

describe("Film Analysis route", () => {
  it("renders at /film-analysis", () => {
    renderAt("/film-analysis");
    expect(screen.getByRole("heading", { level: 1, name: /FILM\s+ANALYSIS/i })).toBeInTheDocument();
  });

  it("renders every workspace panel", () => {
    renderAt("/film-analysis");
    for (const heading of [
      /Upload\s+Film/i,
      /Video\s+Player/i,
      /Play\s+Timeline/i,
      /Evidence\s+Panel/i,
      /Player\s+Selection/i,
      /Final\s+TruGrade/i,
      /Analysis\s+Job/i,
    ]) {
      expect(screen.getByRole("heading", { level: 2, name: heading })).toBeInTheDocument();
    }
  });

  it("offers exactly the 13 supported TruGrade positions, plus the empty prompt", () => {
    renderAt("/film-analysis");
    const select = screen.getByLabelText("Position") as HTMLSelectElement;
    expect(select.tagName).toBe("SELECT");
    const values = Array.from(select.options).map((option) => option.value);
    expect(values[0]).toBe("");
    expect(values.slice(1)).toEqual([
      "QB",
      "RB",
      "WR",
      "Y",
      "H",
      "OT",
      "IOL",
      "DT",
      "DE",
      "JACK",
      "LB",
      "CB",
      "SAFETY",
    ]);
  });

  it("starts with no grade, no confidence and no evidence rather than zeroes", () => {
    renderAt("/film-analysis");
    expect(screen.getByText("Official game grade")).toBeInTheDocument();
    expect(screen.getByText("Confidence —")).toBeInTheDocument();
    expect(
      screen.getByText(/Official trait grades appear only after evidence-supported grading/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Select a graded trait to inspect contributing plays/i)).toBeInTheDocument();
  });
});

describe("navigation", () => {
  it("moves between the two working views without a reload", async () => {
    const user = userEvent.setup();
    renderAt("/");
    const sidebar = screen.getByRole("navigation", { name: "Sections" });
    await user.click(within(sidebar).getByRole("link", { name: /Film Analysis/ }));
    expect(screen.getByRole("heading", { level: 1, name: /FILM\s+ANALYSIS/i })).toBeInTheDocument();
  });

  it("marks the current route active in the sidebar", () => {
    renderAt("/film-analysis");
    const sidebar = screen.getByRole("navigation", { name: "Sections" });
    const link = within(sidebar).getByRole("link", { name: /Film Analysis/ });
    expect(link).toHaveClass("active");
  });

  it("sends an unknown path back to Create Profile", () => {
    renderAt("/not-a-real-route");
    expect(screen.getByRole("heading", { level: 1, name: /CREATE\s+PROFILE/i })).toBeInTheDocument();
  });

  it("carries the profile form across a navigation", async () => {
    const user = userEvent.setup();
    renderAt("/");
    await user.type(screen.getByLabelText("Athlete Name"), "Jordan Williams");

    const sidebar = screen.getByRole("navigation", { name: "Sections" });
    await user.click(within(sidebar).getByRole("link", { name: /Film Analysis/ }));
    await user.click(within(sidebar).getByRole("link", { name: /Create Profile/ }));

    expect(screen.getByLabelText("Athlete Name")).toHaveValue("Jordan Williams");
  });
});

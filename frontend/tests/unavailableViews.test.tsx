import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "@/App";
import { NAV_GROUPS } from "@/navigation";

/**
 * Acceptance guard: no unfinished screen may present generated data as real.
 *
 * These pages are allowed to show their layout. They are not allowed to show a
 * grade, a star rating, an offer probability, a school name, or a count that
 * looks like it came from somewhere.
 */

const SOON_ROUTES = NAV_GROUPS.flatMap((group) => group.items)
  .filter((item) => item.soon)
  .map((item) => item.to);

/** Any bare number that could read as a real measurement or total. */
const NUMERIC_CLAIM = /\b\d+(\.\d+)?%?\b/;

/** Placeholders that are honestly empty rather than fabricated. */
const ALLOWED_LITERALS = ["0 athletes", "Power 4", "Group of 5"];

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("network disabled in tests"))));
});

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("unavailable views", () => {
  it("covers every soon-badged sidebar entry", () => {
    expect(SOON_ROUTES).toHaveLength(5);
  });

  it.each(SOON_ROUTES)("%s says it is not available", (route) => {
    renderAt(route);
    expect(screen.getByText("COMING SOON")).toBeInTheDocument();
    expect(screen.getByText(/Not available yet\./)).toBeInTheDocument();
    expect(
      screen.getByText(/no athlete,\s*grade, or recruiting data is shown on this screen/i),
    ).toBeInTheDocument();
  });

  it.each(SOON_ROUTES)("%s shows no lit star rating", (route) => {
    const { container } = renderAt(route);
    expect(container.querySelectorAll(".star.lit")).toHaveLength(0);
  });

  it.each(SOON_ROUTES)("%s states no numeric value as a result", (route) => {
    const { container } = renderAt(route);

    // Only inspect the placeholder body — the shell's own copy (nav, headings)
    // is not a data claim.
    const body = container.querySelector(".vbody");
    expect(body).not.toBeNull();

    const offenders: string[] = [];
    body!.querySelectorAll<HTMLElement>(".stat-val, .rv, .card-note, .school-name, .score-big").forEach(
      (node) => {
        const text = (node.textContent ?? "").trim();
        if (!text || ALLOWED_LITERALS.includes(text)) return;
        if (NUMERIC_CLAIM.test(text)) offenders.push(text);
      },
    );

    expect(offenders).toEqual([]);
  });
});

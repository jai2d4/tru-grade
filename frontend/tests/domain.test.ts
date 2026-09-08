import { describe, expect, it } from "vitest";
import { TRUGRADE_POSITIONS, normalizePosition, positionLabel } from "@/lib/positions";
import { runSieve, tierStars } from "@/lib/metricSieve";
import { averageMakeupGrade, gradeDown, rankLabel } from "@/lib/makeupGrade";
import { confidencePercent, numericField, orDash } from "@/lib/format";

describe("supported positions", () => {
  it("lists exactly the 13 positions with a rules file", () => {
    expect(TRUGRADE_POSITIONS.map((p) => p.value)).toEqual([
      "QB", "RB", "WR", "Y", "H", "OT", "IOL", "DT", "DE", "JACK", "LB", "CB", "SAFETY",
    ]);
  });

  it("resolves the depth-chart aliases the rules loader accepts", () => {
    expect(normalizePosition("DB")).toBe("CB");
    expect(normalizePosition("DL")).toBe("DT");
    expect(normalizePosition("OL")).toBe("IOL");
    expect(normalizePosition("TE")).toBe("Y");
    expect(normalizePosition("S")).toBe("SAFETY");
  });

  it("is case and whitespace insensitive", () => {
    expect(normalizePosition("  lb ")).toBe("LB");
  });

  it("refuses a position with no rules rather than guessing one", () => {
    expect(normalizePosition("PUNTER")).toBeNull();
    expect(normalizePosition("")).toBeNull();
    expect(normalizePosition(null)).toBeNull();
    expect(positionLabel("PUNTER")).toBe("—");
  });
});

describe("metric sieve", () => {
  const blank = {
    height: null, weight: null, forty: null, shuttle: null,
    bench: null, squat: null, gpa: null, sat: null, act: null,
  };

  it("returns UNRANKED when no measurable was supplied", () => {
    const result = runSieve("DB", blank);
    expect(result.tier).toBe("UNRANKED");
    expect(result.hard_metrics_passed).toBe(false);
    expect(result.qualifying_tiers).toEqual([]);
    expect(tierStars(result)).toBe(0);
  });

  it("never turns a missing measurable into a failure", () => {
    const result = runSieve("DB", { ...blank, height: 72, weight: 190 });
    const forty = result.checks.find((c) => c.metric === "forty_yard_dash");
    expect(forty?.passed).toBeNull();
  });

  it("clears D1 FBS and every easier tier below it", () => {
    const result = runSieve("DB", {
      ...blank, height: 72, weight: 190, forty: 4.5, shuttle: 4.1, gpa: 3.4, sat: 1100,
    });
    expect(result.tier).toBe("D1_FBS");
    expect(result.hard_metrics_passed).toBe(true);
    expect(result.qualifying_tiers).toEqual(["D1_FBS", "D1_FCS", "D2_D3_NAIA_JUCO"]);
    expect(tierStars(result)).toBe(5);
  });

  it("walks down the ladder when a metric misses the top bracket", () => {
    // 4.65s clears the FCS window but not the 4.60s FBS ceiling.
    const result = runSieve("DB", { ...blank, height: 69, weight: 172, forty: 4.65 });
    expect(result.walked[0]).toEqual({ tier: "D1_FBS", passed: false });
    expect(result.tier).toBe("D1_FCS");
    expect(result.qualifying_tiers).toEqual(["D1_FCS", "D2_D3_NAIA_JUCO"]);
    expect(tierStars(result)).toBe(4);
  });

  it("flags the out-of-bracket game changer instead of dropping the athlete", () => {
    // Laser speed at FBS level, frame far outside every bracket.
    const result = runSieve("DB", { ...blank, height: 62, weight: 140, forty: 4.35, shuttle: 4.0 });
    expect(result.is_game_changer).toBe(true);
    expect(result.game_changer_reason).toMatch(/manual review/i);
    expect(tierStars(result)).toBe(5);
  });

  it("treats a missed academic floor as a fail only when neither SAT nor ACT clears", () => {
    const passing = runSieve("QB", {
      ...blank, height: 76, weight: 220, forty: 4.7, gpa: 3.2, sat: 900, act: 22,
    });
    expect(passing.tier).toBe("D1_FBS");

    const failing = runSieve("QB", {
      ...blank, height: 76, weight: 220, forty: 4.7, gpa: 3.2, sat: 900, act: 15,
    });
    expect(failing.tier).not.toBe("D1_FBS");
  });
});

describe("makeup grade", () => {
  it("averages only the grades that were provided", () => {
    expect(averageMakeupGrade({ a: "GAME_CHANGER", b: "WIN_PLUS", c: null })).toBe("ALL_CONF");
    expect(averageMakeupGrade({ a: null })).toBeNull();
  });

  it("grades down one step per tier and never past the top", () => {
    expect(gradeDown("WIN")).toEqual({
      overall: "WIN", p4: "WIN", group_of_5: "WIN_PLUS", fcs: "ALL_CONF", d2_d3_naia_juco: "GAME_CHANGER",
    });
    expect(gradeDown("GAME_CHANGER").d2_d3_naia_juco).toBe("GAME_CHANGER");
  });

  it("passes an unrecognised rank through rather than mislabelling it", () => {
    expect(rankLabel("NGE")).toBe("NGE");
    expect(rankLabel("SOMETHING_NEW")).toBe("SOMETHING_NEW");
  });
});

describe("display helpers keep absent values absent", () => {
  it("shows an em dash for anything the backend did not send", () => {
    expect(orDash(null)).toBe("—");
    expect(orDash(undefined)).toBe("—");
    expect(orDash("")).toBe("—");
    expect(orDash(0)).toBe("0");
  });

  it("does not render a missing confidence as 0%", () => {
    expect(confidencePercent(null)).toBe("Confidence —");
    expect(confidencePercent(0)).toBe("Confidence 0%");
    expect(confidencePercent(0.834)).toBe("Confidence 83%");
  });

  it("parses an empty numeric field as null, not NaN or zero", () => {
    expect(numericField("")).toBeNull();
    expect(numericField("   ")).toBeNull();
    expect(numericField("abc")).toBeNull();
    expect(numericField("0")).toBe(0);
    expect(numericField("72.5")).toBe(72.5);
  });
});

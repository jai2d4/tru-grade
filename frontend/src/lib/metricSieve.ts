/**
 * 1:1 port of the inline metric sieve, which itself mirrors
 * app/services/metric_sieve.py. Thresholds, ladder order, hard-fail rules and
 * the game-changer escape hatch are carried over unchanged — this is a
 * TypeScript translation, not a re-derivation.
 */

export type SievePosition = "QB" | "RB" | "WR" | "TE" | "OL" | "DL" | "DE" | "LB" | "DB";

export interface Thresholds {
  height?: [number, number];
  weight?: [number, number];
  forty?: [number, number];
  shuttle_max?: number;
  bench_min?: number;
  squat_min?: number;
  gpa_min?: number;
  sat_min?: number;
  act_min?: number;
}

export const MATRIX: Record<string, Thresholds> = {
  "QB|D1_FBS": { height: [74, 78], weight: [200, 240], forty: [4.6, 4.9], gpa_min: 3.0, sat_min: 1000, act_min: 18 },
  "QB|D2_D3_NAIA_JUCO": { height: [72, 77], weight: [180, 225], forty: [4.7, 5.0] },
  "RB|D1_FBS": { height: [69, 73], weight: [190, 230], forty: [4.4, 4.6], bench_min: 300, squat_min: 450, gpa_min: 3.0, sat_min: 1000, act_min: 18 },
  "RB|D1_FCS_D2": { height: [68, 72], weight: [180, 220], forty: [4.5, 4.9] },
  "WR|D1_FBS": { height: [72, 76], weight: [180, 220], forty: [4.3, 4.6], gpa_min: 3.0, sat_min: 1000, act_min: 18 },
  "WR|D1_FCS_D2": { height: [70, 75], weight: [170, 210], forty: [4.4, 4.9] },
  "TE|D1_FBS": { height: [76, 79], weight: [230, 270], forty: [4.6, 4.8], bench_min: 300, squat_min: 450, gpa_min: 3.0, sat_min: 1000, act_min: 18 },
  "TE|D1_FCS_D2": { height: [74, 78], weight: [220, 260], forty: [4.7, 5.2] },
  "OL|D1_FBS": { height: [76, 80], weight: [280, 330], forty: [5.0, 5.3], bench_min: 350, squat_min: 500, gpa_min: 3.0, sat_min: 1000, act_min: 18 },
  "OL|D1_FCS_D2": { height: [74, 78], weight: [270, 310] },
  "DL|D1_FBS": { height: [75, 78], weight: [250, 320], forty: [4.8, 5.1], bench_min: 350, squat_min: 500, gpa_min: 3.0, sat_min: 1000, act_min: 18 },
  "DL|D1_FCS": { height: [74, 77], weight: [240, 300], forty: [4.9, 5.2] },
  "DL|D2_D3_NAIA_JUCO": { height: [72, 76], weight: [230, 280], forty: [5.0, 5.3] },
  "DE|D1_FBS": { height: [75, 78], weight: [240, 280], forty: [4.6, 4.8], bench_min: 350, squat_min: 500, gpa_min: 3.0, sat_min: 1000, act_min: 18 },
  "DE|D1_FCS": { height: [74, 77], weight: [230, 270], forty: [4.7, 4.9] },
  "DE|D2_D3_NAIA_JUCO": { height: [72, 76], weight: [220, 260], forty: [4.8, 5.1] },
  "LB|D1_FBS": { height: [73, 76], weight: [220, 250], forty: [4.5, 4.7], gpa_min: 3.0, sat_min: 1000, act_min: 18 },
  "LB|D1_FCS": { height: [72, 75], weight: [210, 240], forty: [4.6, 4.8] },
  "LB|D2_D3_NAIA_JUCO": { height: [71, 74], weight: [200, 230], forty: [4.7, 5.0] },
  "DB|D1_FBS": { height: [70, 74], weight: [175, 210], forty: [4.4, 4.6], shuttle_max: 4.2, gpa_min: 3.0, sat_min: 1000, act_min: 18 },
  "DB|D1_FCS": { height: [69, 73], weight: [170, 200], forty: [4.5, 4.7] },
  "DB|D2_D3_NAIA_JUCO": { height: [68, 72], weight: [165, 190], forty: [4.6, 4.9] },
};

export const LADDER: Record<SievePosition, string[]> = {
  QB: ["D1_FBS", "D2_D3_NAIA_JUCO"],
  RB: ["D1_FBS", "D1_FCS_D2"],
  WR: ["D1_FBS", "D1_FCS_D2"],
  TE: ["D1_FBS", "D1_FCS_D2"],
  OL: ["D1_FBS", "D1_FCS_D2"],
  DL: ["D1_FBS", "D1_FCS", "D2_D3_NAIA_JUCO"],
  DE: ["D1_FBS", "D1_FCS", "D2_D3_NAIA_JUCO"],
  LB: ["D1_FBS", "D1_FCS", "D2_D3_NAIA_JUCO"],
  DB: ["D1_FBS", "D1_FCS", "D2_D3_NAIA_JUCO"],
};

export interface Athlete {
  height: number | null;
  weight: number | null;
  forty: number | null;
  shuttle: number | null;
  bench: number | null;
  squat: number | null;
  gpa: number | null;
  sat: number | null;
  act: number | null;
}

export interface SieveCheck {
  metric: string;
  label: string;
  laser?: boolean;
  value: number | null;
  threshold: string;
  /** null means no data was supplied — never treat that as a failure. */
  passed: boolean | null;
}

export interface SieveResult {
  position: SievePosition;
  tier: string;
  checks: SieveCheck[];
  hard_metrics_passed: boolean;
  is_game_changer: boolean;
  game_changer_reason: string | null;
  qualifying_tiers: string[];
  walked: { tier: string; passed: boolean }[];
}

function inRange(v: number | null, lo: number | null, hi: number | null): boolean | null {
  if (v == null) return null;
  if (lo != null && v < lo) return false;
  if (hi != null && v > hi) return false;
  return true;
}

export function runSieve(pos: SievePosition, a: Athlete): SieveResult {
  let best: SieveResult | null = null;
  const walked: { tier: string; passed: boolean }[] = [];
  const ladder = LADDER[pos];

  for (let i = 0; i < ladder.length; i++) {
    const tier = ladder[i] as string;
    const m = MATRIX[`${pos}|${tier}`] as Thresholds;
    const checks: SieveCheck[] = [];

    if (m.forty) checks.push({ metric: "forty_yard_dash", label: "40-yd dash", laser: true, value: a.forty, threshold: `${m.forty[0]}–${m.forty[1]}s`, passed: inRange(a.forty, null, m.forty[1]) });
    if (m.shuttle_max) checks.push({ metric: "pro_agility_shuttle", label: "Pro-agility", laser: true, value: a.shuttle, threshold: `≤ ${m.shuttle_max}s`, passed: inRange(a.shuttle, null, m.shuttle_max) });
    if (m.height) checks.push({ metric: "height_in", label: "Height", value: a.height, threshold: `${m.height[0]}–${m.height[1]} in`, passed: inRange(a.height, m.height[0], m.height[1]) });
    if (m.weight) checks.push({ metric: "weight_lbs", label: "Weight", value: a.weight, threshold: `${m.weight[0]}–${m.weight[1]} lbs`, passed: inRange(a.weight, m.weight[0], m.weight[1]) });
    if (m.bench_min) checks.push({ metric: "bench_lbs", label: "Bench", value: a.bench, threshold: `≥ ${m.bench_min} lbs`, passed: inRange(a.bench, m.bench_min, null) });
    if (m.squat_min) checks.push({ metric: "squat_lbs", label: "Squat", value: a.squat, threshold: `≥ ${m.squat_min} lbs`, passed: inRange(a.squat, m.squat_min, null) });
    if (m.gpa_min) checks.push({ metric: "gpa", label: "GPA", value: a.gpa, threshold: `≥ ${m.gpa_min}`, passed: inRange(a.gpa, m.gpa_min, null) });
    if (m.sat_min && a.sat != null) checks.push({ metric: "sat", label: "SAT", value: a.sat, threshold: `≥ ${m.sat_min}`, passed: inRange(a.sat, m.sat_min, null) });
    if (m.act_min && a.act != null) checks.push({ metric: "act", label: "ACT", value: a.act, threshold: `≥ ${m.act_min}`, passed: inRange(a.act, m.act_min, null) });

    let hardFail = checks.some((c) => c.passed === false && !["sat", "act"].includes(c.metric));
    const acad = checks.filter((c) => ["sat", "act"].includes(c.metric));
    if (acad.length && !acad.some((c) => c.passed)) hardFail = true;

    const res: SieveResult = {
      position: pos,
      tier,
      checks,
      hard_metrics_passed: !hardFail,
      is_game_changer: false,
      game_changer_reason: null,
      qualifying_tiers: [],
      walked,
    };

    // No data provided at all → cannot project a tier.
    if (checks.every((c) => c.passed == null)) {
      res.hard_metrics_passed = false;
      res.tier = "UNRANKED";
      res.walked = walked;
      return res;
    }

    if (!hardFail) {
      // Clearing this tier implies clearing every easier one below it.
      res.qualifying_tiers = ladder.slice(i);
      walked.push({ tier, passed: true });
      res.walked = walked;
      return res;
    }

    walked.push({ tier, passed: false });
    if (!best) best = res;
  }

  const result = best as SieveResult;
  const laser = result.checks.filter((c) => c.laser);
  const frame = result.checks.filter((c) => ["height_in", "weight_lbs"].includes(c.metric));
  if (
    laser.length &&
    laser.every((c) => c.passed !== false) &&
    laser.some((c) => c.passed) &&
    frame.some((c) => c.passed === false)
  ) {
    result.is_game_changer = true;
    result.game_changer_reason =
      "Laser metrics meet or beat D1 FBS thresholds despite out-of-bracket frame. Flag for Truth Report Panel manual review.";
    result.qualifying_tiers = [result.tier];
  } else {
    result.tier = "UNRANKED";
  }
  result.walked = walked;
  return result;
}

/**
 * TruStar Rating — purely presentational mapping from the real projected tier
 * onto a 5-star readout, echoing the wireframe deck's rating widget. Narrowed
 * to the two fields it actually reads so callers holding a persisted
 * evaluation's metric_sieve_results (a slightly different generated type,
 * missing the client-only `walked` ladder) can pass it directly.
 */
export function tierStars(r: Pick<SieveResult, "tier" | "is_game_changer">): number {
  if (r.is_game_changer) return 5;
  const map: Record<string, number> = {
    D1_FBS: 5,
    D1_FCS: 4,
    D1_FCS_D2: 4,
    D2_D3_NAIA_JUCO: 3,
    UNRANKED: 0,
  };
  return map[r.tier] ?? 0;
}

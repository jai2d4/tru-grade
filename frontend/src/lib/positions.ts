/**
 * The 13 supported TruGrade positions.
 *
 * This list is the frontend mirror of `backend/grading/rules/*.json` — one rule
 * file per position, which is what `load_position_rules` accepts. Sending
 * anything else makes the Truth Report fail with "Unsupported TruGrade
 * position", which is why Phase 16 replaces the old free-text position input
 * with this fixed set.
 *
 * `aliases` reproduces backend/grading/rules_loader.POSITION_ALIASES so the
 * familiar depth-chart labels still resolve to the right rule file.
 */

export const TRUGRADE_POSITIONS = [
  { value: "QB", label: "QB — Quarterback" },
  { value: "RB", label: "RB — Running Back" },
  { value: "WR", label: "WR — Wide Receiver" },
  { value: "Y", label: "Y — Tight End (in-line)" },
  { value: "H", label: "H — Flex / Move Tight End" },
  { value: "OT", label: "OT — Offensive Tackle" },
  { value: "IOL", label: "IOL — Interior Offensive Line" },
  { value: "DT", label: "DT — Defensive Tackle" },
  { value: "DE", label: "DE — Defensive End" },
  { value: "JACK", label: "JACK — Edge / Outside Linebacker" },
  { value: "LB", label: "LB — Linebacker" },
  { value: "CB", label: "CB — Cornerback" },
  { value: "SAFETY", label: "SAFETY — Safety" },
] as const;

export type TruGradePosition = (typeof TRUGRADE_POSITIONS)[number]["value"];

/** Mirrors backend/grading/rules_loader.POSITION_ALIASES. */
const ALIASES: Record<string, TruGradePosition> = {
  DB: "CB",
  DL: "DT",
  OL: "IOL",
  TE: "Y",
  S: "SAFETY",
};

const SUPPORTED = new Set<string>(TRUGRADE_POSITIONS.map((p) => p.value));

/**
 * Resolve a stored or typed position onto a supported rule file, the same way
 * `normalize_position` does on the server. Returns null when the value is not
 * gradeable, so callers can say so instead of guessing a position.
 */
export function normalizePosition(value: string | null | undefined): TruGradePosition | null {
  if (!value) return null;
  const upper = value.trim().toUpperCase();
  if (!upper) return null;
  const resolved = ALIASES[upper] ?? upper;
  return SUPPORTED.has(resolved) ? (resolved as TruGradePosition) : null;
}

export function positionLabel(value: string | null | undefined): string {
  const resolved = normalizePosition(value);
  if (!resolved) return "—";
  return TRUGRADE_POSITIONS.find((p) => p.value === resolved)?.label ?? resolved;
}

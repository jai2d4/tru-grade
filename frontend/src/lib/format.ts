/**
 * Display helpers. Every one of these keeps "no value" visibly distinct from
 * "zero" — the UI must never round an absent measurement into a number.
 */

/** Report timestamp, same format the Phase 15 page stamped onto the report. */
export function reportStamp(now: Date = new Date()): string {
  const date = now.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  const time = now.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${date} · ${time}`;
}

/** Percentage readout for a 0–1 confidence. Absent confidence stays absent. */
export function confidencePercent(confidence: number | null | undefined): string {
  if (confidence == null) return "Confidence —";
  return `Confidence ${Math.round(confidence * 100)}%`;
}

/** Seconds, at the same one-decimal precision the evidence panel already used. */
export function seconds(value: number): string {
  return `${value.toFixed(1)}s`;
}

/** Em dash for anything the backend did not supply. */
export function orDash(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

/** Trait keys arrive snake_cased from the grading engine. */
export function humanizeTrait(name: string): string {
  return name.replaceAll("_", " ");
}

/** Analysis statuses arrive snake_cased too. */
export function humanizeStatus(status: string): string {
  return status.replaceAll("_", " ");
}

/** Parse a numeric form field, preserving empty as null rather than 0 or NaN. */
export function numericField(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number.parseFloat(value);
  return Number.isNaN(parsed) ? null : parsed;
}

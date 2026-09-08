/**
 * API origin resolution — carried over unchanged from the Phase 15 page.
 *
 * When the page is served BY the FastAPI app itself (locally on :8000, or from
 * the deployed Render URL) `location.origin` is already the API's own origin,
 * so a relative path just works. The Vite dev server runs on :5173, so that
 * one case is redirected to :8000. Opening the built file directly off disk
 * (file://) has no usable origin, so fall back to localhost:8000.
 */
export function apiBase(): string {
  if (typeof location === "undefined") return "http://localhost:8000";
  if (location.port === "5173") {
    return `${location.protocol}//${location.hostname}:8000`;
  }
  return location.origin.startsWith("http") ? location.origin : "http://localhost:8000";
}

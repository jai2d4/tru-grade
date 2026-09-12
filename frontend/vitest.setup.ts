import "@testing-library/jest-dom/vitest";

// jsdom implements neither of these, and both are exercised by the film
// workspace (object URLs for local playback, canvas for the tracking overlay).
if (!URL.createObjectURL) {
  URL.createObjectURL = () => "blob:trugrade-test";
}
if (!URL.revokeObjectURL) {
  URL.revokeObjectURL = () => undefined;
}

// jsdom has no layout engine, so scrollTo/scrollIntoView are unimplemented and
// would log a "Not implemented" error on every routed render.
window.scrollTo = () => undefined;
Element.prototype.scrollIntoView = () => undefined;

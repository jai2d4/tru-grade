/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  // Root-relative asset URLs. The Phase 16 migration used "./" so the bundle
  // would work from any mount point — but the FastAPI SPA fallback
  // (backend/main.py) serves this same index.html verbatim at every
  // client-side route (e.g. /coach/dashboard on reload), and a relative
  // "./assets/…" resolves against *that* URL, not the file's location on
  // disk — it would ask the browser for /coach/assets/… and 404. The app is
  // always mounted at the domain root, so "/" is the correct base, not a
  // regression from the original intent.
  base: "/",
  build: { outDir: "dist", emptyOutDir: true, sourcemap: true },
  server: {
    // Phase 15 served the page on :5173 and called the API on :8000. The API
    // base in src/api/base.ts keeps that rule; this proxy makes it optional.
    port: 5173,
  },
  test: {
    globals: true,
    environment: "jsdom",
    // Pinned so tests can assert absolute API URLs.
    environmentOptions: { jsdom: { url: "http://localhost:3000" } },
    setupFiles: ["./vitest.setup.ts"],
    css: false,
    include: ["tests/**/*.test.{ts,tsx}"],
  },
});

/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  // Relative asset URLs so the built bundle works from any mount point the
  // FastAPI app chooses to serve it from.
  base: "./",
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

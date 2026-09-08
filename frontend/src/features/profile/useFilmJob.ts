import { useCallback, useEffect, useRef, useState } from "react";
import { scout } from "@/api/client";
import type { FilmAnalysis } from "@/api/types";
import type { PipelineStep } from "@/components/chrome";

/**
 * Module 1 film upload — the async Gemini grading job behind Create Profile.
 *
 * The Phase 15 script posted the multipart form, then polled the job every five
 * seconds until it completed or failed, redrawing a three-step pipeline each
 * time. That is preserved exactly, including the poll interval and the pipeline
 * copy. There is no demo fallback: when grading fails the UI says so.
 */

const POLL_MS = 5000;

export type FilmMode = "live" | "error" | null;

export interface FilmState {
  name: string | null;
  mode: FilmMode;
  analysis: FilmAnalysis | null;
}

export const EMPTY_FILM: FilmState = { name: null, mode: null, analysis: null };

export interface UseFilmJob {
  film: FilmState;
  steps: PipelineStep[] | null;
  /** The file name or URL line shown above the pipeline. */
  label: string | null;
  submitFile: (file: File, playerIdentifier: string) => Promise<void>;
  submitYoutube: (url: string, playerIdentifier: string) => Promise<void>;
  /** Rejected before any request — bad extension or a non-YouTube URL. */
  rejection: string | null;
}

const VIDEO_EXTENSIONS = /\.(mp4|mov|avi)$/i;
const YOUTUBE_URL = /^https?:\/\/(www\.|m\.)?(youtube\.com|youtu\.be)\//i;

interface UseFilmJobOptions {
  /** Called once a submission settles, so the report can be regenerated. */
  onSettled: (film: FilmState) => void;
}

export function useFilmJob({ onSettled }: UseFilmJobOptions): UseFilmJob {
  const [film, setFilm] = useState<FilmState>(EMPTY_FILM);
  const [steps, setSteps] = useState<PipelineStep[] | null>(null);
  const [label, setLabel] = useState<string | null>(null);
  const [rejection, setRejection] = useState<string | null>(null);
  const cancelled = useRef(false);

  useEffect(() => {
    cancelled.current = false;
    return () => {
      cancelled.current = true;
    };
  }, []);

  /**
   * `uploadedLabel` carries the file size on the first paint only; every later
   * repaint falls back to the bare name, matching the original two labels.
   */
  const submit = useCallback(
    async (form: FormData, name: string, uploadedLabel: string) => {
      setRejection(null);
      setLabel(uploadedLabel);
      setSteps([
        { label: "upload received", state: "done" },
        { label: "sending to gemini-3.5-flash…", state: "active" },
        { label: "awaiting analysis", state: "" },
      ]);

      let settled: FilmState;
      try {
        const created = await scout.createFilmJob(form);
        let analysis: FilmAnalysis | undefined;

        for (;;) {
          await new Promise((resolve) => setTimeout(resolve, POLL_MS));
          if (cancelled.current) return;
          const status = await scout.filmJob(created.job_id);
          if (status.status === "failed") {
            throw new Error(status.error || "Real Gemini grading failed");
          }
          if (status.status === "complete") {
            analysis = status.result?.analysis;
            break;
          }
          setLabel(name);
          setSteps([
            { label: "upload received", state: "done" },
            { label: status.message || "Gemini is processing the film", state: "active" },
            { label: "real grades will appear when complete", state: "" },
          ]);
        }

        settled = { name, mode: "live", analysis: analysis ?? null };
        setLabel(name);
        setSteps([
          { label: "upload received", state: "done" },
          { label: "gemini-3.5-flash ingestion", state: "done" },
          { label: "analysis complete — LIVE API", state: "done" },
        ]);
      } catch (error) {
        settled = { name, mode: "error", analysis: null };
        setLabel(name);
        setSteps([
          { label: "upload received", state: "done" },
          { label: "real Gemini grading failed", state: "err" },
          { label: error instanceof Error ? error.message : "Unknown error", state: "err" },
        ]);
      }

      if (cancelled.current) return;
      setFilm(settled);
      onSettled(settled);
    },
    [onSettled],
  );

  const submitFile = useCallback(
    async (file: File, playerIdentifier: string) => {
      if (!VIDEO_EXTENSIONS.test(file.name)) {
        setSteps(null);
        setLabel(null);
        setRejection("Invalid video format (.mp4 / .mov / .avi)");
        return;
      }
      const form = new FormData();
      form.append("file", file);
      if (playerIdentifier) form.append("player_identifier", playerIdentifier);
      const megabytes = (file.size / 1048576).toFixed(1);
      await submit(form, file.name, `${file.name} · ${megabytes} MB`);
    },
    [submit],
  );

  const submitYoutube = useCallback(
    async (url: string, playerIdentifier: string) => {
      if (!YOUTUBE_URL.test(url)) {
        setSteps(null);
        setLabel(null);
        setRejection("Not a valid YouTube URL");
        return;
      }
      const form = new FormData();
      form.append("youtube_url", url);
      if (playerIdentifier) form.append("player_identifier", playerIdentifier);
      await submit(form, url, url);
    },
    [submit],
  );

  return { film, steps, label, submitFile, submitYoutube, rejection };
}

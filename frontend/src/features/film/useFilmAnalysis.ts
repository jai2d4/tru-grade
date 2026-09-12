import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { analysis, players, videos } from "@/api/client";
import type {
  AnalysisJob,
  DemoTrait,
  DemoTraitName,
  Evidence,
  GradeRecord,
  Play,
  Track,
  TrackAssignment,
} from "@/api/types";
import { normalizePosition } from "@/lib/positions";
import { useProfile } from "@/state/ProfileContext";

/**
 * The Phase 9 film workspace, ported from the `v2*` functions.
 *
 * Timings, request order, and every status string are carried over: a 3s poll
 * for the analysis job, the automatic identity pass, the automatic field
 * calibration, and the Truth Report poll. Nothing here invents a grade — an
 * ungraded trait stays UNKNOWN, and an uncertain jersey match asks for manual
 * confirmation rather than picking a track.
 */

const POLL_MS = 3000;
const VIDEO_EXTENSIONS = /\.(mp4|mov|avi|mkv)$/i;

export interface Progress {
  percent: number;
  status: string;
}

/** One row of the "Analysis Job" card. */
export interface JobDetailRow {
  label: string;
  value: string;
}

export interface TraitRow {
  name: string;
  label: string;
  score: number | null;
  /** Present only for a graded trait; UNKNOWN traits expose no evidence. */
  evidence: Evidence[] | null;
}

export interface IdentityFields {
  jersey: string;
  position: string;
  playerId: string;
  team: string;
}

const EMPTY_IDENTITY: IdentityFields = { jersey: "", position: "", playerId: "", team: "" };

const DEMO_TRAIT_LABELS: Record<DemoTraitName, string> = {
  field_speed: "Field Speed",
  contact: "Contact",
  play_recognition: "Play Recognition",
  tackling: "Tackling",
  versatility: "Versatility",
};

export function useFilmAnalysis(videoRef: RefObject<HTMLVideoElement>) {
  const { readProfile } = useProfile();

  const [videoId, setVideoId] = useState<string | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [videoName, setVideoName] = useState("No film loaded");
  const [progress, setProgress] = useState<Progress>({ percent: 0, status: "Awaiting film" });
  const [jobDetail, setJobDetail] = useState<JobDetailRow[] | null>(null);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [plays, setPlays] = useState<Play[]>([]);
  const [assignments, setAssignments] = useState<Record<string, TrackAssignment>>({});
  const [selectedTrack, setSelectedTrack] = useState<number | null>(null);
  const [identity, setIdentity] = useState<IdentityFields>(EMPTY_IDENTITY);
  const [assignStatus, setAssignStatus] = useState("");
  const [grade, setGrade] = useState<number | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [traits, setTraits] = useState<TraitRow[] | null>(null);
  const [traitsMessage, setTraitsMessage] = useState<string | null>(
    "Official trait grades appear only after evidence-supported grading.",
  );
  const [evidence, setEvidence] = useState<Evidence[] | null>(null);
  const [overlayOn, setOverlayOn] = useState(true);
  /** Percentage shown in place of the confidence line while a report builds. */
  const [reportProgress, setReportProgress] = useState<number | null>(null);

  // Mutable mirrors, so the poll chains can read current values without being
  // re-created on every state change.
  const cancelled = useRef(false);
  const videoIdRef = useRef<string | null>(null);
  const selectedRef = useRef<number | null>(null);
  const identityRef = useRef(identity);
  const fileUrlRef = useRef<string | null>(null);
  videoIdRef.current = videoId;
  selectedRef.current = selectedTrack;
  identityRef.current = identity;
  fileUrlRef.current = fileUrl;

  useEffect(() => {
    cancelled.current = false;
    return () => {
      cancelled.current = true;
      if (fileUrlRef.current) URL.revokeObjectURL(fileUrlRef.current);
    };
  }, []);

  const setProgressState = useCallback((value: number, status: string) => {
    const percent = Math.max(0, Math.min(100, Number(value) || 0));
    setProgress({ percent, status: status || "Processing" });
  }, []);

  const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

  /* ---------- Truth Report ---------- */

  const renderTruthReport = useCallback((report: GradeRecord | undefined) => {
    if (!report) return;
    setGrade(report.game_grade ?? null);
    setConfidence(report.confidence ?? 0);
    const demo = report.demo_traits ?? {};
    setTraits(
      (Object.entries(demo) as [DemoTraitName, DemoTrait][]).map(([name, value]) => ({
        name,
        label: DEMO_TRAIT_LABELS[name] ?? name,
        score: value.status === "graded" ? value.score : null,
        evidence: value.status === "graded" ? value.evidence : null,
      })),
    );
    setTraitsMessage(null);
  }, []);

  const pollTruthReport = useCallback(
    async (playerId: string) => {
      const id = videoIdRef.current;
      if (!id) return;
      try {
        for (;;) {
          const job = await players.truthReport(playerId, id);
          if (cancelled.current) return;
          if (job.status !== "completed" && job.status !== "failed") {
            setConfidence(null);
            setTraitsMessage(null);
            setReportProgress(job.progress || 0);
            await wait(POLL_MS);
            if (cancelled.current) return;
            continue;
          }
          if (job.status === "failed") {
            throw new Error(job.error || job.message || "Truth Report failed.");
          }
          setReportProgress(null);
          renderTruthReport(job.report);
          return;
        }
      } catch (error) {
        setReportProgress(null);
        setTraits(null);
        setTraitsMessage(`Truth Report failed: ${messageOf(error)}`);
      }
    },
    [renderTruthReport],
  );

  const startTruthReport = useCallback(async () => {
    const track = selectedRef.current;
    const id = videoIdRef.current;
    if (track == null || !id) return;

    const fields = identityRef.current;
    const jersey = fields.jersey.trim();
    const playerId = fields.playerId.trim() || `jersey-${jersey}`;
    const position = normalizePosition(fields.position);
    if (!position) {
      setTraits(null);
      setTraitsMessage("Select the player position to apply the correct TruGrade rules.");
      return;
    }
    try {
      await players.startTruthReport(playerId, { video_id: id, track_id: track, position });
      if (cancelled.current) return;
      setTraits(null);
      setTraitsMessage("Building the evidence-backed Truth Report…");
      void pollTruthReport(playerId);
    } catch (error) {
      setTraits(null);
      setTraitsMessage(messageOf(error));
    }
  }, [pollTruthReport]);

  /* ---------- existing grades for an assigned player ---------- */

  const loadGrade = useCallback(async (playerId: string) => {
    try {
      const data = await players.grades(playerId);
      if (cancelled.current) return;
      const latest = data.grades?.at(-1);
      if (!latest) return;
      setGrade(latest.game_grade ?? null);
      setConfidence(latest.confidence ?? 0);
      // A null trait means the engine had no evidence for it. The Phase 15 page
      // dropped those rows rather than showing a zero, so keep doing that.
      const positionTraits = latest.position_grade?.traits ?? {};
      const rows: TraitRow[] = [];
      for (const [name, value] of Object.entries(positionTraits)) {
        if (!value) continue;
        rows.push({
          name,
          label: name.replaceAll("_", " "),
          score: value.score,
          evidence: value.evidence,
        });
      }
      setTraits(rows.length ? rows : null);
      setTraitsMessage(rows.length ? null : "No supported trait grades yet.");
    } catch (error) {
      setTraits(null);
      setTraitsMessage(messageOf(error));
    }
  }, []);

  /* ---------- automatic identity ---------- */

  const pollAutomaticIdentity = useCallback(async () => {
    const id = videoIdRef.current;
    if (!id) return;
    try {
      for (;;) {
        const result = await videos.identifyStatus(id);
        if (cancelled.current) return;
        if (result.status === "processing") {
          await wait(POLL_MS);
          if (cancelled.current) return;
          continue;
        }
        if (result.status === "failed") {
          throw new Error(result.error || result.status_detail || "Automatic identification failed");
        }
        if (result.status === "identified" && result.selected_track_id != null) {
          setSelectedTrack(result.selected_track_id);
          selectedRef.current = result.selected_track_id;
          const refreshed = await videos.tracks(id);
          if (cancelled.current) return;
          setAssignments(refreshed.assignments ?? {});
          setAssignStatus(
            `Automatically identified Track ${result.selected_track_id} at ${Math.round(
              result.confidence * 100,
            )}% confidence. Confirm if correct.`,
          );
          void startTruthReport();
        } else {
          setAssignStatus(
            "Jersey evidence was uncertain. Select the correct track and confirm—TruGrade did not guess.",
          );
        }
        return;
      }
    } catch (error) {
      setAssignStatus(`Automatic identification failed: ${messageOf(error)}`);
    }
  }, [startTruthReport]);

  const startAutomaticIdentity = useCallback(async () => {
    const id = videoIdRef.current;
    if (!id) return;
    const profile = readProfile();
    const fields = identityRef.current;
    // Same fallback as before: the workspace's own fields first, then whatever
    // Create Profile collected.
    const jersey = (fields.jersey || profile.playerNumber).trim();
    const colors = (fields.team || profile.schoolColors).trim();
    if (!jersey || !colors) {
      setAssignStatus("Enter the player number and school colors to identify automatically.");
      return;
    }
    try {
      await videos.startIdentify(id, {
        jersey_number: jersey,
        school_colors: colors,
        player_id: fields.playerId.trim() || null,
        position: normalizePosition(fields.position),
      });
      if (cancelled.current) return;
      setAssignStatus(`Searching every tracked frame for #${jersey}…`);
      void pollAutomaticIdentity();
    } catch (error) {
      setAssignStatus(`Automatic identification failed: ${messageOf(error)}`);
    }
  }, [pollAutomaticIdentity, readProfile]);

  /* ---------- automatic field calibration ---------- */

  const startAutomaticCalibration = useCallback(async () => {
    const id = videoIdRef.current;
    if (!id) return;
    try {
      const result = await videos.autoCalibrate(id);
      if (cancelled.current) return;
      const label =
        result.status === "calibrated"
          ? `Field scale estimated at ${Math.round(result.confidence * 100)}% · ${
              result.tracks_calibrated ?? 0
            } tracks measured; confirm field points for verified yards`
          : "Field needs manual calibration — yard-based speed will remain unknown.";
      setJobDetail((rows) => [...(rows ?? []), { label: "Field", value: label }]);
      if (result.status === "calibrated") {
        const refreshed = await videos.tracks(id);
        if (cancelled.current) return;
        if (refreshed.tracks) setTracks(refreshed.tracks);
      }
    } catch {
      setJobDetail((rows) => [...(rows ?? []), { label: "Field", value: "Calibration unavailable" }]);
    }
  }, []);

  /* ---------- results ---------- */

  const loadResults = useCallback(async () => {
    const id = videoIdRef.current;
    if (!id) return;
    const [trackData, playData] = await Promise.all([videos.tracks(id), videos.plays(id)]);
    if (cancelled.current) return;
    setTracks(trackData.tracks ?? []);
    setAssignments(trackData.assignments ?? {});
    setPlays(playData.plays ?? []);
    setProgressState(100, "Analysis complete — identifying the requested player");
    void startAutomaticIdentity();
    void startAutomaticCalibration();
  }, [setProgressState, startAutomaticCalibration, startAutomaticIdentity]);

  const pollJob = useCallback(
    async (jobId: string) => {
      try {
        for (;;) {
          const job: AnalysisJob = await analysis.status(jobId);
          if (cancelled.current) return;
          setProgressState(job.progress, job.message || job.status.replaceAll("_", " "));
          setJobDetail([
            { label: "Status", value: job.status },
            { label: "Frames", value: job.frame_count?.toString() ?? "—" },
            { label: "Tracks", value: job.track_count?.toString() ?? "—" },
          ]);
          if (job.status === "failed") throw new Error(job.error || "Analysis failed");
          if (job.status === "completed") {
            await loadResults();
            return;
          }
          await wait(POLL_MS);
          if (cancelled.current) return;
        }
      } catch (error) {
        setProgressState(0, `Analysis failed: ${messageOf(error)}`);
      }
    },
    [loadResults, setProgressState],
  );

  /* ---------- upload ---------- */

  const uploadFilm = useCallback(
    async (file: File | undefined) => {
      if (!file) return;
      if (!VIDEO_EXTENSIONS.test(file.name)) {
        setProgressState(0, "Use an MP4, MOV, AVI, or MKV file.");
        return;
      }
      if (fileUrlRef.current) URL.revokeObjectURL(fileUrlRef.current);
      const url = URL.createObjectURL(file);
      fileUrlRef.current = url;
      setFileUrl(url);
      setVideoName(file.name);
      setProgressState(2, "Uploading film in protected chunks…");
      try {
        const uploaded = await videos.upload(file);
        if (cancelled.current) return;
        setVideoId(uploaded.video_id);
        videoIdRef.current = uploaded.video_id;
        const job = await analysis.start(uploaded.video_id);
        if (cancelled.current) return;
        setProgressState(job.progress, job.message ?? "");
        void pollJob(job.job_id);
      } catch (error) {
        setProgressState(0, `Upload failed: ${messageOf(error)}`);
      }
    },
    [pollJob, setProgressState],
  );

  /* ---------- manual track selection and confirmation ---------- */

  const selectTrack = useCallback(
    (trackId: number) => {
      setSelectedTrack(trackId);
      selectedRef.current = trackId;
      const a: Partial<TrackAssignment> = assignments[String(trackId)] ?? {};
      const next: IdentityFields = {
        jersey: a.jersey_number ?? "",
        position: a.position ?? "",
        playerId: a.player_id ?? "",
        team: a.team ?? "",
      };
      setIdentity(next);
      identityRef.current = next;
      if (a.player_id) void loadGrade(a.player_id);
    },
    [assignments, loadGrade],
  );

  const assignTrack = useCallback(async () => {
    const track = selectedRef.current;
    const id = videoIdRef.current;
    if (track == null || !id) {
      setAssignStatus("Select a track first.");
      return;
    }
    const fields = identityRef.current;
    try {
      const result = await videos.assignTrack(id, track, {
        player_id: fields.playerId.trim() || null,
        jersey_number: fields.jersey.trim(),
        team: fields.team.trim() || null,
        position: normalizePosition(fields.position),
        reason: "Human confirmed identity in Film Analysis",
      });
      if (cancelled.current) return;
      setAssignments((prev) => ({ ...prev, [String(track)]: result }));
      setAssignStatus(`Confirmed Track ${result.track_id} as #${result.jersey_number}.`);
      if (result.player_id) void loadGrade(result.player_id);
      void startTruthReport();
    } catch (error) {
      setAssignStatus(`Assignment failed: ${messageOf(error)}`);
    }
  }, [loadGrade, startTruthReport]);

  const updateIdentity = useCallback((patch: Partial<IdentityFields>) => {
    setIdentity((prev) => {
      const next = { ...prev, ...patch };
      identityRef.current = next;
      return next;
    });
  }, []);

  /* ---------- playback ---------- */

  const seek = useCallback(
    (seconds: number) => {
      const video = videoRef.current;
      if (!video) return;
      video.currentTime = seconds;
      void video.play().catch(() => {});
    },
    [videoRef],
  );

  return {
    videoId,
    fileUrl,
    videoName,
    progress,
    jobDetail,
    tracks,
    plays,
    assignments,
    selectedTrack,
    identity,
    assignStatus,
    grade,
    confidence,
    reportProgress,
    traits,
    traitsMessage,
    evidence,
    overlayOn,
    setOverlayOn,
    setEvidence,
    uploadFilm,
    selectTrack,
    assignTrack,
    updateIdentity,
    seek,
  };
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

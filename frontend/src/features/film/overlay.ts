import type { Track, TrackPosition } from "@/api/types";

/**
 * Port of `v2DrawOverlay`.
 *
 * Draws the selected track's box for whichever sample sits closest to the
 * current playback time. The letterbox maths, colours, line width and label
 * font are unchanged.
 */
export function drawOverlay(
  canvas: HTMLCanvasElement,
  video: HTMLVideoElement,
  tracks: Track[],
  selectedTrack: number | null,
  enabled: boolean,
): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  canvas.width = video.clientWidth;
  canvas.height = video.clientHeight;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!enabled || selectedTrack == null || !video.videoWidth) return;

  const track = tracks.find((item) => item.track_id === selectedTrack);
  if (!track) return;

  const ms = video.currentTime * 1000;
  const point = (track.positions ?? []).reduce<TrackPosition | null>(
    (best, item) =>
      !best || Math.abs(item.timestamp_ms - ms) < Math.abs(best.timestamp_ms - ms) ? item : best,
    null,
  );
  if (!point) return;

  const scale = Math.min(canvas.width / video.videoWidth, canvas.height / video.videoHeight);
  const ox = (canvas.width - video.videoWidth * scale) / 2;
  const oy = (canvas.height - video.videoHeight * scale) / 2;
  const [x1, y1, x2, y2] = point.bbox;

  ctx.strokeStyle = "#7FB0FF";
  ctx.lineWidth = 3;
  ctx.shadowColor = "#2F7DFF";
  ctx.shadowBlur = 12;
  ctx.strokeRect(ox + x1 * scale, oy + y1 * scale, (x2 - x1) * scale, (y2 - y1) * scale);

  ctx.fillStyle = "#2F7DFF";
  ctx.shadowBlur = 0;
  ctx.font = "600 13px IBM Plex Mono";
  ctx.fillText(`TRACK ${track.track_id}`, ox + x1 * scale, Math.max(14, oy + y1 * scale - 6));
}

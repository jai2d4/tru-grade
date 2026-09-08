import { useCallback, useEffect, useRef } from "react";
import { Icon } from "@/components/IconSprite";
import { ViewHeader } from "@/components/chrome";
import { confidencePercent, orDash, seconds } from "@/lib/format";
import { TRUGRADE_POSITIONS } from "@/lib/positions";
import { drawOverlay } from "./overlay";
import { useFilmAnalysis } from "./useFilmAnalysis";

/**
 * Film Analysis — the Phase 9 workspace, now at `/film-analysis`.
 *
 * Layout, card order and copy are unchanged. The one deliberate change is the
 * position control: it was a free-text input, and is now a select over the 13
 * positions that have grading rules, so a typo can no longer send an
 * ungradeable position to the Truth Report.
 */
export function FilmAnalysisPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const film = useFilmAnalysis(videoRef);

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    drawOverlay(canvas, video, film.tracks, film.selectedTrack, film.overlayOn);
  }, [film.overlayOn, film.selectedTrack, film.tracks]);

  // Phase 15 attached this listener once results loaded; attaching it for the
  // life of the page is equivalent and survives a re-render.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.addEventListener("timeupdate", redraw);
    redraw();
    return () => video.removeEventListener("timeupdate", redraw);
  }, [redraw]);

  return (
    <div className="view">
      <ViewHeader
        title={
          <>
            FILM <span className="accent">ANALYSIS</span>
          </>
        }
        subtitle="Upload game film, track the athlete, verify every play, and inspect the evidence behind the grade."
        badge="TRUGRADE V2"
        badgeStyle={{ color: "var(--blue-2)" }}
      />

      <div className="film-workspace">
        <div className="film-grid">
          <div className="film-stack">
            {/* ---------- upload ---------- */}
            <section className="card">
              <div className="film-toolbar">
                <h2 style={{ margin: 0 }}>
                  <Icon name="upload" />
                  Upload <span className="accent">Film</span>
                </h2>
                <span className="pill pass">LOCAL BY DEFAULT</span>
              </div>
              <label className="drop" htmlFor="v2FilmInput">
                <Icon name="upload" className="drop-icon" />
                <div>Choose full game film</div>
                <div className="drop-sub">
                  MP4 · MOV · AVI · MKV · processing continues in background
                </div>
              </label>
              <input
                id="v2FilmInput"
                type="file"
                accept=".mp4,.mov,.avi,.mkv,video/*"
                hidden
                onChange={(event) => void film.uploadFilm(event.target.files?.[0])}
              />
              <div
                className="progress-track"
                role="progressbar"
                aria-valuenow={film.progress.percent}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Film analysis progress"
              >
                <div className="progress-fill" style={{ width: `${film.progress.percent}%` }} />
              </div>
              <div className="film-status-line" role="status" aria-live="polite">
                <span>{film.progress.status}</span>
                <span>{film.progress.percent}%</span>
              </div>
            </section>

            {/* ---------- player ---------- */}
            <section className="card">
              <div className="film-toolbar">
                <h2 style={{ margin: 0 }}>
                  <Icon name="play" />
                  Video <span className="accent">Player</span>
                </h2>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={film.overlayOn}
                    onChange={(event) => film.setOverlayOn(event.target.checked)}
                  />{" "}
                  Tracking overlay
                </label>
              </div>
              <div className="film-player">
                <video
                  ref={videoRef}
                  controls
                  playsInline
                  {...(film.fileUrl ? { src: film.fileUrl } : {})}
                />
                <canvas ref={canvasRef} />
              </div>
              <div className="film-status-line" style={{ marginTop: 9 }}>
                <span>{film.videoName}</span>
                <span>Vision device appears after analysis</span>
              </div>
            </section>

            {/* ---------- play timeline ---------- */}
            <section className="card">
              <h2>
                <Icon name="film" />
                Play <span className="accent">Timeline</span>
              </h2>
              <div className="compact-list">
                {film.plays.length ? (
                  film.plays.map((play) => (
                    <button
                      type="button"
                      className="compact-row"
                      key={play.play_id}
                      onClick={() => film.seek(play.snap_time)}
                    >
                      <strong>{play.play_id}</strong>
                      <span>
                        {seconds(play.snap_time)} · {Math.round(play.confidence * 100)}% {play.source}
                      </span>
                    </button>
                  ))
                ) : (
                  <div className="film-empty">
                    Analyzed plays will appear here. Select a play to jump to its exact timestamp.
                  </div>
                )}
              </div>
            </section>

            {/* ---------- evidence ---------- */}
            <section className="card">
              <h2>
                <Icon name="target" />
                Evidence <span className="accent">Panel</span>
              </h2>
              {film.evidence === null ? (
                <div className="film-empty">
                  Select a graded trait to inspect contributing plays and timestamps.
                </div>
              ) : film.evidence.length ? (
                <div className="compact-list">
                  {film.evidence.map((item, index) => (
                    <button
                      type="button"
                      className="compact-row"
                      key={`${item.play_id}-${index}`}
                      onClick={() => film.seek(item.timestamp_start)}
                    >
                      <strong>{item.play_id}</strong>
                      <span>
                        {seconds(item.timestamp_start)} · {item.description}
                      </span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="film-empty">No timestamped evidence was attached to this trait.</div>
              )}
            </section>
          </div>

          <aside className="film-stack">
            {/* ---------- player selection ---------- */}
            <section className="card">
              <h2>
                <Icon name="users" />
                Player <span className="accent">Selection</span>
              </h2>
              <div className="compact-list">
                {film.tracks.length ? (
                  film.tracks.map((track) => {
                    const assigned = film.assignments[String(track.track_id)] ?? {};
                    return (
                      <button
                        type="button"
                        className={
                          film.selectedTrack === track.track_id ? "compact-row selected" : "compact-row"
                        }
                        aria-pressed={film.selectedTrack === track.track_id}
                        key={track.track_id}
                        onClick={() => film.selectTrack(track.track_id)}
                      >
                        <strong>TRACK {track.track_id}</strong>
                        <span>
                          {assigned.jersey_number
                            ? `#${assigned.jersey_number}`
                            : `${track.frames?.length ?? 0} frames`}
                        </span>
                      </button>
                    );
                  })
                ) : (
                  <div className="film-empty">Tracks will appear after detection.</div>
                )}
              </div>

              <div className="subdivider">Confirm jersey assignment</div>

              <div className="row2">
                <div className="field">
                  <div className="fbody">
                    <label htmlFor="v2Jersey">Jersey #</label>
                    <input
                      id="v2Jersey"
                      inputMode="numeric"
                      maxLength={2}
                      placeholder="12"
                      value={film.identity.jersey}
                      onChange={(event) => film.updateIdentity({ jersey: event.target.value })}
                    />
                  </div>
                </div>
                <div className="field">
                  <div className="fbody">
                    <label htmlFor="v2Position">Position</label>
                    <select
                      id="v2Position"
                      value={film.identity.position}
                      onChange={(event) => film.updateIdentity({ position: event.target.value })}
                    >
                      <option value="">Select position</option>
                      {TRUGRADE_POSITIONS.map((position) => (
                        <option value={position.value} key={position.value}>
                          {position.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              <div className="field">
                <div className="fbody">
                  <label htmlFor="v2PlayerId">Player ID or name</label>
                  <input
                    id="v2PlayerId"
                    placeholder="Player identifier"
                    value={film.identity.playerId}
                    onChange={(event) => film.updateIdentity({ playerId: event.target.value })}
                  />
                </div>
              </div>
              <div className="field">
                <div className="fbody">
                  <label htmlFor="v2Team">Team / uniform</label>
                  <input
                    id="v2Team"
                    placeholder="Red, white, black"
                    value={film.identity.team}
                    onChange={(event) => film.updateIdentity({ team: event.target.value })}
                  />
                </div>
              </div>

              <button
                className="btn-solid"
                type="button"
                style={{ width: "100%", justifyContent: "center" }}
                onClick={() => void film.assignTrack()}
              >
                <Icon name="check" className="sm" />
                Confirm Player
              </button>
              <div className="card-note" style={{ marginTop: 9 }} role="status" aria-live="polite">
                {film.assignStatus}
              </div>
            </section>

            {/* ---------- grade ---------- */}
            <section className="card">
              <h2>
                <Icon name="chart" />
                Final <span className="accent">TruGrade</span>
              </h2>
              <div className="score-lockup">
                <div className="score-big">{orDash(film.grade)}</div>
                <div>
                  <div className="score-caption">Official game grade</div>
                  <div className="stat-val">
                    {film.reportProgress != null
                      ? `Report ${film.reportProgress}%`
                      : confidencePercent(film.confidence)}
                  </div>
                </div>
              </div>
              <div>
                {film.traits ? (
                  film.traits.map((trait) =>
                    trait.score == null ? (
                      <div className="compact-row" key={trait.name}>
                        <span>{trait.label}</span>
                        <strong>UNKNOWN</strong>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="compact-row"
                        key={trait.name}
                        onClick={() => film.setEvidence(trait.evidence ?? [])}
                      >
                        <span>{trait.label}</span>
                        <strong>{trait.score}</strong>
                      </button>
                    ),
                  )
                ) : (
                  <div className="film-empty">{film.traitsMessage}</div>
                )}
              </div>
            </section>

            {/* ---------- job ---------- */}
            <section className="card">
              <h2>
                <Icon name="shield" />
                Analysis <span className="accent">Job</span>
              </h2>
              {film.jobDetail ? (
                <div>
                  {film.jobDetail.map((row, index) => (
                    <div className="trait-row" key={`${row.label}-${index}`}>
                      <span>{row.label}</span>
                      <b>{row.value}</b>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="film-empty">No active job.</div>
              )}
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}

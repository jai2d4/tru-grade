import { useCallback, useRef, useState, type ChangeEvent, type DragEvent, type KeyboardEvent } from "react";
import { ApiError, scout } from "@/api/client";
import type { LookupSource } from "@/api/types";
import { Icon } from "@/components/IconSprite";
import { PageHead, Pipeline, TopBar, TrustBar } from "@/components/chrome";
import { numericField, reportStamp } from "@/lib/format";
import { runSieve } from "@/lib/metricSieve";
import { useProfile, type ProfileState } from "@/state/ProfileContext";
import { TruthReportPanel, type GeneratedReport } from "./TruthReportPanel";
import { useFilmJob, type FilmState } from "./useFilmJob";

/**
 * Create Profile — the Phase 15 default view, now at `/`.
 *
 * The sieve still runs against the DB thresholds. That position was hardcoded
 * before this migration and is deliberately left alone: the sieve's nine-slot
 * taxonomy (app/services/metric_sieve.py) is a different list from the thirteen
 * graded positions in backend/grading/rules, and picking one here would change
 * what the report claims. See docs/PHASE16_UI_MIGRATION.md.
 */

const SIEVE_POSITION = "DB" as const;

interface LookupStatus {
  message: string;
  sources: LookupSource[];
  /** True once a lookup returned but produced no public source. */
  noSources: boolean;
}

export function CreateProfilePage() {
  // The form lives in shared state so Film Analysis can still fall back to the
  // player number and school colors entered here.
  const { profile: form, setProfile: setForm, readProfile } = useProfile();
  const [lookup, setLookup] = useState<LookupStatus | null>(null);
  const [report, setReport] = useState<GeneratedReport | null>(null);
  const [dragging, setDragging] = useState(false);
  const filePickRef = useRef<HTMLInputElement>(null);

  /**
   * The Phase 15 `run()`: the report is a snapshot taken at generation time,
   * not a live mirror of the form, so typing into a field does not silently
   * rewrite an already-issued report.
   */
  const generate = useCallback((film: FilmState) => {
    const current = readProfile();
    const sieve = runSieve(SIEVE_POSITION, {
      height: numericField(current.height),
      weight: numericField(current.weight),
      forty: null,
      shuttle: null,
      bench: null,
      squat: null,
      gpa: numericField(current.gpa),
      sat: null,
      act: null,
    });
    setReport({
      sieve,
      playerNumber: current.playerNumber.trim(),
      stamp: reportStamp(),
      film,
    });
  }, [readProfile]);

  const filmJob = useFilmJob({ onSettled: generate });

  const field = (key: keyof ProfileState) => ({
    value: form[key],
    onChange: (event: ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [key]: event.target.value })),
  });

  /** Port of `playerIdentifier()` — what the AI is told to track. */
  const playerIdentifier = useCallback(() => {
    const { athleteName, playerNumber, schoolColors, school } = readProfile();
    return [
      athleteName.trim(),
      playerNumber.trim() ? `jersey #${playerNumber.trim()}` : "",
      schoolColors.trim() ? `${schoolColors.trim()} uniform colors` : "",
      school.trim(),
    ]
      .filter(Boolean)
      .join(", ");
  }, [readProfile]);

  const onLookup = useCallback(async () => {
    const name = readProfile().athleteName.trim();
    const school = readProfile().school.trim();
    if (!name) {
      setLookup({ message: "Enter the player's full name first.", sources: [], noSources: false });
      return;
    }
    setLookup({
      message: "Searching public sources for verified player data…",
      sources: [],
      noSources: false,
    });
    try {
      const data = await scout.playerLookup({ player_name: name, school: school || null });

      // Only overwrite a field the lookup actually returned; a blank or missing
      // value must never clear something the user typed.
      setForm((prev) => {
        const next = { ...prev };
        const set = (key: keyof ProfileState, value: unknown) => {
          if (value === null || value === undefined || value === "") return;
          next[key] = String(value);
        };
        set("athleteName", data.full_name);
        set("school", data.school);
        set(
          "schoolColors",
          Array.isArray(data.school_colors) ? data.school_colors.join(", ") : data.school_colors,
        );
        set("classYear", data.grad_year);
        set("stateInput", data.state);
        set("playerNumber", data.jersey_number);
        set("height", data.height_in);
        set("weight", data.weight_lbs);
        set("gpa", data.gpa);
        return next;
      });

      const sources = data.sources ?? [];
      setLookup({
        message: data.verification_note || "Lookup complete.",
        sources,
        noSources: sources.length === 0,
      });
      generate(filmJob.film);
    } catch (error) {
      const message = error instanceof ApiError || error instanceof Error ? error.message : "Unknown error";
      setLookup({ message: `Lookup failed: ${message}`, sources: [], noSources: false });
    }
  }, [filmJob.film, generate, readProfile, setForm]);

  const onPickFile = (file: File | undefined) => {
    if (!file) return;
    void filmJob.submitFile(file, playerIdentifier());
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    onPickFile(event.dataTransfer.files[0]);
  };

  const onDropKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      filePickRef.current?.click();
    }
  };

  return (
    <div className="view">
      <TopBar />
      <PageHead
        title={
          <>
            CREATE <span className="accent">PROFILE</span>
          </>
        }
        subtitle="Build your athlete profile. Our AI will do the rest."
      />

      <div className="wrap">
        <div className="card">
          <div className="field">
            <Icon name="user" />
            <div className="fbody">
              <label htmlFor="athleteName">Athlete Name</label>
              <input id="athleteName" type="text" placeholder="Jordan Williams" {...field("athleteName")} />
            </div>
          </div>

          <div className="row3">
            <div className="field">
              <Icon name="helmet" />
              <div className="fbody">
                <label htmlFor="playerNumber">Player Number to Track</label>
                <input
                  id="playerNumber"
                  type="number"
                  min="0"
                  max="99"
                  placeholder="12"
                  {...field("playerNumber")}
                />
              </div>
            </div>
            <div className="field">
              <Icon name="book" />
              <div className="fbody">
                <label htmlFor="classYear">Class Year</label>
                <input id="classYear" type="number" placeholder="2027" {...field("classYear")} />
              </div>
            </div>
            <div className="field">
              <Icon name="flag" />
              <div className="fbody">
                <label htmlFor="stateInput">State</label>
                <input id="stateInput" type="text" maxLength={2} placeholder="TX" {...field("stateInput")} />
              </div>
            </div>
          </div>

          <div className="row2">
            <div className="field">
              <Icon name="shield" />
              <div className="fbody">
                <label htmlFor="school">School</label>
                <input id="school" type="text" placeholder="Westview High School" {...field("school")} />
              </div>
            </div>
            <div className="field">
              <Icon name="star" />
              <div className="fbody">
                <label htmlFor="schoolColors">School Colors</label>
                <input
                  id="schoolColors"
                  type="text"
                  placeholder="Red, white, black"
                  {...field("schoolColors")}
                />
              </div>
            </div>
          </div>

          <button className="btn-solid" type="button" onClick={() => void onLookup()}>
            Look Up Verified Player Data
          </button>
          <div id="lookupstatus" className="card-note" style={{ margin: "10px 0 14px" }} role="status">
            {lookup ? (
              <>
                {lookup.message}
                {lookup.sources.length ? (
                  <>
                    <br />
                    Sources:{" "}
                    {lookup.sources.map((source, index) => (
                      <span key={source.url}>
                        {index > 0 ? " · " : null}
                        <a href={source.url} target="_blank" rel="noopener noreferrer">
                          {source.title || "Source"}
                        </a>
                      </span>
                    ))}
                  </>
                ) : lookup.noSources ? (
                  <>
                    <br />
                    No public source was returned; no unverified fields were filled.
                  </>
                ) : null}
              </>
            ) : null}
          </div>

          <div className="row2">
            <div className="field">
              <Icon name="ruler" />
              <div className="fbody">
                <label htmlFor="height">Height (in)</label>
                <input id="height" type="number" step="0.5" placeholder="72" {...field("height")} />
              </div>
            </div>
            <div className="field">
              <Icon name="scale" />
              <div className="fbody">
                <label htmlFor="weight">Weight (lbs)</label>
                <input id="weight" type="number" placeholder="190" {...field("weight")} />
              </div>
            </div>
          </div>

          <div className="field">
            <Icon name="book" />
            <div className="fbody">
              <label htmlFor="gpa">GPA</label>
              <input id="gpa" type="number" step="0.01" placeholder="3.2" {...field("gpa")} />
            </div>
          </div>

          <h2 id="film-anchor" style={{ marginTop: 24 }}>
            <Icon name="play" />
            Film <span className="accent">Upload</span> — Module 1
          </h2>
          <div className="card-note" style={{ marginBottom: 12 }}>
            The AI tracks the player number and school colors entered above. It will not substitute
            another player.
          </div>

          <div
            className={dragging ? "drop over" : "drop"}
            id="drop"
            role="button"
            tabIndex={0}
            aria-label="Drop game film here or press Enter to browse"
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => filePickRef.current?.click()}
            onKeyDown={onDropKey}
          >
            <Icon name="upload" className="drop-icon" />
            <div>Drop game film here or click to browse</div>
            <div className="drop-sub">.mp4 · .mov · .avi</div>
          </div>
          <input
            id="filepick"
            ref={filePickRef}
            type="file"
            accept=".mp4,.mov,.avi,video/*"
            style={{ display: "none" }}
            onChange={(event) => onPickFile(event.target.files?.[0])}
          />

          <label htmlFor="ytUrl" style={{ margin: "12px 0 4px" }}>
            Or paste a YouTube link
          </label>
          <div className="row2" style={{ gridTemplateColumns: "1fr auto", alignItems: "center" }}>
            <div className="field" style={{ margin: 0 }}>
              <Icon name="play" />
              <div className="fbody">
                <input id="ytUrl" type="url" placeholder="https://youtube.com/watch?v=…" {...field("ytUrl")} />
              </div>
            </div>
            <button
              className="btn-solid"
              type="button"
              onClick={() => void filmJob.submitYoutube(form.ytUrl.trim(), playerIdentifier())}
            >
              Analyze <Icon name="chevron" className="sm" />
            </button>
          </div>

          <div id="filmstatus" role="status" aria-live="polite">
            {filmJob.rejection ? (
              <Pipeline steps={[{ label: filmJob.rejection, state: "err" }]} />
            ) : filmJob.steps ? (
              <>
                {filmJob.label ? <div className="filmname">{filmJob.label}</div> : null}
                <Pipeline steps={filmJob.steps} />
              </>
            ) : null}
          </div>
        </div>

        <TruthReportPanel report={report} />
      </div>

      <TrustBar />
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import {
  athletes as athletesApi,
  coachNotes as notesApi,
  evaluations as evaluationsApi,
  fitScores as fitScoresApi,
} from "@/api/coachClient";
import type { Athlete, CoachFitScores, CoachNote, Evaluation, FilmGrade, FilmLink } from "@/api/types";
import { GRADE_DOWN_ROWS } from "@/features/athlete/TraitBreakdownPage";
import { Icon } from "@/components/IconSprite";
import { Stars, ViewHeader } from "@/components/chrome";
import { confidencePercent, orDash } from "@/lib/format";
import { rankLabel } from "@/lib/makeupGrade";
import { tierStars } from "@/lib/metricSieve";

/**
 * Coach 360 — one real page combining everything already on record for an
 * athlete: the verified hard-metric sieve, Profile & Makeup grade-down,
 * coach fit scores, coach notes, linked film, and V2 deterministic grades.
 * Every number here comes from an endpoint another screen already reads —
 * this page adds no new data model, just a single view of it.
 *
 * Two pieces of the original wireframe are deliberately left out rather
 * than faked: an AI-generated narrative summary (no reasoning pipeline
 * produces that) and a recorded coach decision (Offer / Invite / Pass —
 * a real feature, but one that needs its own schema and a product decision
 * on the exact decision states, not just a read of what already exists).
 * Both say so plainly instead of showing invented content.
 */
export function Coach360ReportPage() {
  const [searchParams] = useSearchParams();
  const athleteId = searchParams.get("athleteId");

  return (
    <div className="view">
      <ViewHeader
        title={
          <>
            COACH 360 <span className="accent">TRUTH REPORT</span>
          </>
        }
        subtitle="Complete player evaluation. Verified truth. Confident decisions."
      />
      <div className="vbody">
        {athleteId ? (
          <Loaded athleteId={athleteId} />
        ) : (
          <p className="unavailable-note" role="note">
            <Icon name="clock" />
            <span>
              <b>No athlete selected.</b> Open the{" "}
              <Link to="/coach/board" style={{ color: "var(--blue-2)" }}>
                Recruitment Board
              </Link>{" "}
              and choose one to view their 360 report.
            </span>
          </p>
        )}
      </div>
    </div>
  );
}

function Loaded({ athleteId }: { athleteId: string }) {
  const [athlete, setAthlete] = useState<Athlete | null>(null);
  const [evaluationList, setEvaluationList] = useState<Evaluation[] | null>(null);
  const [scores, setScores] = useState<CoachFitScores | null>(null);
  const [notes, setNotes] = useState<CoachNote[] | null>(null);
  const [filmLinks, setFilmLinks] = useState<FilmLink[] | null>(null);
  const [grades, setGrades] = useState<FilmGrade[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      athletesApi.get(athleteId),
      evaluationsApi.list(athleteId),
      fitScoresApi.get(athleteId),
      notesApi.list(athleteId),
      athletesApi.filmLinks(athleteId),
      athletesApi.grades(athleteId),
    ])
      .then(([athleteResult, evaluationsResult, scoresResult, notesResult, filmLinksResult, gradesResult]) => {
        setAthlete(athleteResult);
        setEvaluationList(evaluationsResult);
        setScores(scoresResult);
        setNotes(notesResult);
        setFilmLinks(filmLinksResult);
        setGrades(gradesResult);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof ApiError && err.status === 404
            ? "This athlete could not be found."
            : "Could not reach the TruGrade backend.",
        );
      })
      .finally(() => setLoading(false));
  }, [athleteId]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <p className="unavailable-note" role="alert">
        <Icon name="x" />
        <span>{error}</span>
      </p>
    );
  }
  if (loading || !athlete) {
    return <p className="card-note">Loading…</p>;
  }

  const latest = (evaluationList ?? [])[0] ?? null;
  const sieve = latest?.metric_sieve_results ?? null;
  const strengths = sieve?.checks.filter((check) => check.passed === true) ?? [];
  const weaknesses = sieve?.checks.filter((check) => check.passed === false) ?? [];
  const fitCategories: { key: keyof CoachFitScores & string; label: string }[] = [
    { key: "scheme_fit", label: "Scheme Fit" },
    { key: "culture_fit", label: "Culture Fit" },
    { key: "need_match", label: "Need Match" },
    { key: "development", label: "Development" },
  ];

  return (
    <>
      <div className="card">
        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          <div className="avatar-ring" style={{ width: 56, height: 56 }}>
            <svg className="ic" style={{ width: 24, height: 24 }} aria-hidden="true">
              <use href="#ic-user" />
            </svg>
          </div>
          <div>
            <h3 style={{ margin: 0 }}>
              {athlete.first_name} {athlete.last_name}
            </h3>
            <p className="card-note" style={{ margin: 0 }}>
              {athlete.position}
              {athlete.school ? ` · ${athlete.school}` : ""}
              {athlete.grad_year ? ` · Class of ${athlete.grad_year}` : ""}
            </p>
          </div>
        </div>
      </div>

      <div className="rating-card">
        <div className="rating-label">TRUSTAR RATING</div>
        {sieve ? (
          <>
            <Stars count={tierStars(sieve)} label={`Projected tier ${sieve.tier.replaceAll("_", " ")}`} />
            <p className="card-note">
              Hard metrics {sieve.hard_metrics_passed ? "cleared" : "not cleared"} · {sieve.checks.length}{" "}
              metric{sieve.checks.length === 1 ? "" : "s"} checked
              {latest?.is_game_changer ? " · Game Changer" : ""}
            </p>
          </>
        ) : (
          <>
            <Stars count={0} label="Not yet rated" />
            <p className="card-note">No Truth Report has been run for this athlete yet.</p>
          </>
        )}
      </div>

      <div className="cards-3">
        <div className="card">
          <h3>
            <Icon name="shield" />
            Truth Reports on File
          </h3>
          <div className="stat-val" style={{ fontSize: 22 }}>
            {evaluationList?.length ?? 0}
          </div>
        </div>
        <div className="card">
          <h3>
            <Icon name="film" />
            Linked Film
          </h3>
          <div className="stat-val" style={{ fontSize: 22 }}>
            {filmLinks?.length ?? 0}
          </div>
        </div>
        <div className="card">
          <h3>
            <Icon name="chart" />
            V2 Grades
          </h3>
          <div className="stat-val" style={{ fontSize: 22 }}>
            {grades?.length ?? 0}
          </div>
        </div>
      </div>

      <div className="cards-2">
        <div className="card">
          <h3>
            <Icon name="check" />
            Strengths
          </h3>
          {strengths.length > 0 ? (
            <div className="compact-list">
              {strengths.map((check) => (
                <div className="compact-row" key={check.metric}>
                  <span>{check.metric.replaceAll("_", " ")}</span>
                  <strong>{check.athlete_value ?? "—"}</strong>
                </div>
              ))}
            </div>
          ) : (
            <p className="card-note">No hard metrics have cleared their threshold yet.</p>
          )}
        </div>
        <div className="card">
          <h3>
            <Icon name="x" />
            Weaknesses
          </h3>
          {weaknesses.length > 0 ? (
            <div className="compact-list">
              {weaknesses.map((check) => (
                <div className="compact-row" key={check.metric}>
                  <span>{check.metric.replaceAll("_", " ")}</span>
                  <strong>{check.athlete_value ?? "—"}</strong>
                </div>
              ))}
            </div>
          ) : (
            <p className="card-note">No hard metrics have missed their threshold.</p>
          )}
        </div>
      </div>
      {sieve ? (
        <p className="card-note">
          Values and thresholds in full on{" "}
          <Link to={`/athlete/traits?athleteId=${athleteId}&evaluationId=${latest?.id}`} style={{ color: "var(--blue-2)" }}>
            Trait Breakdown
          </Link>
          .
        </p>
      ) : null}

      <div className="card">
        <h3>
          <Icon name="star" />
          Profile &amp; Makeup Grade-Down
        </h3>
        {latest?.makeup_grade_down ? (
          <div className="row-list">
            {GRADE_DOWN_ROWS.map((row) => (
              <div className="row-item" key={row.key}>
                <div className="rl">{row.label}</div>
                <div className="rv">{rankLabel(latest.makeup_grade_down![row.key])}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="card-note">No Profile &amp; Makeup grade was recorded on this report.</p>
        )}
      </div>

      <div className="card">
        <h3>
          <Icon name="target" />
          Coach Fit
        </h3>
        <div className="row-list">
          {fitCategories.map((category) => (
            <div className="row-item" key={category.key}>
              <div className="rl">{category.label}</div>
              <div className="rv">{scores?.[category.key] != null ? `${scores[category.key]} / 5` : "Not yet rated"}</div>
            </div>
          ))}
        </div>
        <p className="card-note" style={{ marginTop: 9 }}>
          Rate or update fit on{" "}
          <Link to={`/coach/player-profile?athleteId=${athleteId}`} style={{ color: "var(--blue-2)" }}>
            Player Profile
          </Link>
          .
        </p>
      </div>

      <div className="card">
        <h3>
          <Icon name="message" />
          Coach Notes
        </h3>
        {notes && notes.length > 0 ? (
          <div className="row-list">
            {notes.map((note) => (
              <div className="row-item" key={note.id} style={{ alignItems: "flex-start" }}>
                <div className="rl" style={{ flexDirection: "column", alignItems: "flex-start" }}>
                  <span>{note.note}</span>
                </div>
                <div className="rv">
                  {note.author ? `${note.author} · ` : ""}
                  {new Date(note.created_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="card-note">No notes yet.</p>
        )}
      </div>

      <div className="card">
        <h3>
          <Icon name="film" />
          Linked Film
        </h3>
        {filmLinks && filmLinks.length > 0 ? (
          <div className="row-list">
            {filmLinks.map((link) => (
              <div className="row-item" key={`${link.video_id}-${link.track_id}`}>
                <div className="rl">
                  {link.filename}
                  {link.confirmed ? "" : " (proposed, not confirmed)"}
                </div>
                <div className="rv">
                  {link.jersey_number ? `#${link.jersey_number}` : "—"} ·{" "}
                  {new Date(link.updated_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="card-note">
            No film linked yet. Confirm this athlete's track in{" "}
            <Link to="/film-analysis" style={{ color: "var(--blue-2)" }}>
              Film Analysis
            </Link>{" "}
            to link one.
          </p>
        )}
      </div>

      <div className="card">
        <h3>
          <Icon name="chart" />
          V2 Grades
        </h3>
        {grades && grades.length > 0 ? (
          <div className="row-list">
            {grades.map((grade) => (
              <div className="row-item" key={grade.id}>
                <div className="rl">
                  {grade.position} · {new Date(grade.created_at).toLocaleDateString()}
                </div>
                <div className="rv">
                  {orDash(grade.game_grade)} · {confidencePercent(grade.confidence)}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="card-note">No deterministic grades run yet.</p>
        )}
      </div>

      <div className="card">
        <h3>
          <Icon name="target" />
          Coach Decision
        </h3>
        <p className="card-note">
          Recording a decision (Offer, Invite, Continue Evaluation, Not a Fit) isn't built yet — it
          needs its own record on the athlete, not just a read of data that already exists elsewhere.
          Use Coach Notes above to log a decision until that lands.
        </p>
        <div className="presets">
          {[
            "Offer — Full Scholarship",
            "Offer — Preferred Walk-On",
            "Invite — Official Visit",
            "Continue Evaluation",
            "Not a Fit",
          ].map((chip) => (
            <button className="chip" type="button" disabled style={{ opacity: 0.6 }} key={chip}>
              {chip}
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

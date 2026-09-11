import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { athletes as athletesApi, coachNotes as notesApi, fitScores as fitScoresApi } from "@/api/coachClient";
import type { Athlete, CoachFitScores, CoachNote, FilmGrade, FilmLink } from "@/api/types";
import { Icon } from "@/components/IconSprite";
import { Stars, ViewHeader } from "@/components/chrome";
import { confidencePercent, orDash } from "@/lib/format";

type FitCategory = "scheme_fit" | "culture_fit" | "need_match" | "development";

const FIT_CATEGORIES: { key: FitCategory; label: string; icon: "target" | "users" | "shield" | "chart" }[] = [
  { key: "scheme_fit", label: "Scheme Fit", icon: "target" },
  { key: "culture_fit", label: "Culture Fit", icon: "users" },
  { key: "need_match", label: "Need Match", icon: "shield" },
  { key: "development", label: "Development", icon: "chart" },
];

/** Coach's view of one athlete — real notes and fit scores, chosen from the Recruitment Board. */
export function PlayerProfilePage() {
  const [searchParams] = useSearchParams();
  const athleteId = searchParams.get("athleteId");

  if (!athleteId) {
    return (
      <div className="view">
        <ViewHeader
          title={
            <>
              PLAYER <span className="accent">PROFILE</span>
            </>
          }
          subtitle="Coach view — verified evidence, film, and recruiting fit."
        />
        <div className="vbody">
          <p className="unavailable-note" role="note">
            <Icon name="clock" />
            <span>
              <b>No athlete selected.</b> Open the{" "}
              <Link to="/coach/board" style={{ color: "var(--blue-2)" }}>
                Recruitment Board
              </Link>{" "}
              and choose one to view their profile.
            </span>
          </p>
        </div>
      </div>
    );
  }

  return <LoadedPlayerProfile athleteId={athleteId} />;
}

function LoadedPlayerProfile({ athleteId }: { athleteId: string }) {
  const [athlete, setAthlete] = useState<Athlete | null>(null);
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
      athletesApi.get(athleteId), fitScoresApi.get(athleteId), notesApi.list(athleteId),
      athletesApi.filmLinks(athleteId), athletesApi.grades(athleteId),
    ])
      .then(([athleteResult, scoresResult, notesResult, filmLinksResult, gradesResult]) => {
        setAthlete(athleteResult);
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

  const ratedCount = scores
    ? FIT_CATEGORIES.filter((category) => scores[category.key] != null).length
    : 0;
  const average =
    scores && ratedCount > 0
      ? FIT_CATEGORIES.reduce((sum, category) => sum + (scores[category.key] ?? 0), 0) / ratedCount
      : 0;

  return (
    <div className="view">
      <ViewHeader
        title={
          <>
            PLAYER <span className="accent">PROFILE</span>
          </>
        }
        subtitle="Coach view — verified evidence, film, and recruiting fit."
      />
      <div className="vbody">
        {error ? (
          <p className="unavailable-note" role="alert">
            <Icon name="x" />
            <span>{error}</span>
          </p>
        ) : loading ? (
          <p className="card-note">Loading…</p>
        ) : athlete ? (
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
                  <Stars
                    count={ratedCount > 0 ? Math.round(average) : 0}
                    label={ratedCount > 0 ? `Average coach fit: ${average.toFixed(1)} of 5` : "Not yet rated"}
                  />
                </div>
              </div>
            </div>

            <FitScoresCard athleteId={athleteId} scores={scores} onSaved={load} />

            <div className="card">
              <h3>
                <Icon name="message" />
                Coach Notes
              </h3>
              <CoachNotesList notes={notes ?? []} />
              <AddNoteForm athleteId={athleteId} onAdded={load} />
            </div>

            <div className="card">
              <h3>
                <Icon name="film" />
                Linked Film
              </h3>
              <FilmLinksList links={filmLinks ?? []} />
            </div>

            <div className="card">
              <h3>
                <Icon name="chart" />
                V2 Grades
              </h3>
              <GradesList grades={grades ?? []} />
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

function FitScoresCard({
  athleteId,
  scores,
  onSaved,
}: {
  athleteId: string;
  scores: CoachFitScores | null;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<Record<FitCategory, number | null>>({
    scheme_fit: scores?.scheme_fit ?? null,
    culture_fit: scores?.culture_fit ?? null,
    need_match: scores?.need_match ?? null,
    development: scores?.development ?? null,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDraft({
      scheme_fit: scores?.scheme_fit ?? null,
      culture_fit: scores?.culture_fit ?? null,
      need_match: scores?.need_match ?? null,
      development: scores?.development ?? null,
    });
  }, [scores]);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await fitScoresApi.set(athleteId, draft);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save fit scores.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="cards-4">
      {FIT_CATEGORIES.map((category) => (
        <div className="card" key={category.key}>
          <h3>
            <Icon name={category.icon} />
            {category.label}
          </h3>
          <div className="field">
            <div className="fbody">
              <label htmlFor={`fit-${category.key}`}>1 (low) – 5 (high)</label>
              <select
                id={`fit-${category.key}`}
                value={draft[category.key] ?? ""}
                onChange={(event) =>
                  setDraft((prev) => ({
                    ...prev,
                    [category.key]: event.target.value === "" ? null : Number(event.target.value),
                  }))
                }
              >
                <option value="">Not yet rated</option>
                {[1, 2, 3, 4, 5].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      ))}
      <div style={{ gridColumn: "1 / -1", display: "flex", alignItems: "center", gap: 10 }}>
        <button className="btn-solid" type="button" onClick={() => void save()} disabled={saving}>
          {saving ? "Saving…" : "Save Fit Scores"}
        </button>
        {error ? (
          <span className="card-note" style={{ color: "var(--fail)" }}>
            {error}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function CoachNotesList({ notes }: { notes: CoachNote[] }) {
  if (notes.length === 0) {
    return <p className="card-note">No notes yet.</p>;
  }
  return (
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
  );
}

function FilmLinksList({ links }: { links: FilmLink[] }) {
  if (links.length === 0) {
    return (
      <p className="card-note">
        No film linked yet. Confirm this athlete's track in{" "}
        <Link to="/film-analysis" style={{ color: "var(--blue-2)" }}>
          Film Analysis
        </Link>{" "}
        to link one.
      </p>
    );
  }
  return (
    <div className="row-list">
      {links.map((link) => (
        <div className="row-item" key={`${link.video_id}-${link.track_id}`}>
          <div className="rl">
            {link.filename}
            {link.confirmed ? "" : " (proposed, not confirmed)"}
          </div>
          <div className="rv">
            {link.jersey_number ? `#${link.jersey_number}` : "—"}
            {link.team ? ` · ${link.team}` : ""}
            {link.position ? ` · ${link.position}` : ""} · {new Date(link.updated_at).toLocaleDateString()}
          </div>
        </div>
      ))}
    </div>
  );
}

function GradesList({ grades }: { grades: FilmGrade[] }) {
  if (grades.length === 0) {
    return (
      <p className="card-note">
        No deterministic grades yet. Run a Truth Report against this athlete's linked film in{" "}
        <Link to="/film-analysis" style={{ color: "var(--blue-2)" }}>
          Film Analysis
        </Link>
        .
      </p>
    );
  }
  return (
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
  );
}

function AddNoteForm({ athleteId, onAdded }: { athleteId: string; onAdded: () => void }) {
  const [note, setNote] = useState("");
  const [author, setAuthor] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!note.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await notesApi.add(athleteId, { note: note.trim(), author: author.trim() || null });
      setNote("");
      onAdded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save that note.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ marginTop: 12 }}>
      <div className="field">
        <Icon name="message" />
        <div className="fbody">
          <label htmlFor="new-note">Add a note</label>
          <input
            id="new-note"
            type="text"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="What did you see?"
          />
        </div>
      </div>
      <div className="row2" style={{ marginTop: 8, alignItems: "center" }}>
        <div className="field">
          <Icon name="user" />
          <div className="fbody">
            <label htmlFor="note-author">Your name (optional)</label>
            <input id="note-author" type="text" value={author} onChange={(event) => setAuthor(event.target.value)} />
          </div>
        </div>
        <button className="chip" type="button" onClick={() => void submit()} disabled={saving || !note.trim()}>
          {saving ? "Saving…" : "Add Note"}
        </button>
      </div>
      {error ? (
        <p className="card-note" style={{ color: "var(--fail)" }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

import { useEffect, useState } from "react";
import { ApiError } from "@/api/client";
import { athletes as athletesApi } from "@/api/coachClient";
import type { Athlete } from "@/api/types";
import { Icon } from "@/components/IconSprite";

interface AthletePickerProps {
  /** The linked athletes.id, or "" for no link — a legitimate state, not a
   * missing one (not every tracked player is a known prospect). */
  athleteId: string;
  onChange: (athleteId: string) => void;
}

/**
 * Links a confirmed track to a real roster athlete, alongside the existing
 * free-text "Player ID or name" field (kept as-is — an opponent or unknown
 * player is still a valid track identity with no roster link at all). See
 * db/init_schema.sql's film_track_assignments comment for why this exists.
 */
export function AthletePicker({ athleteId, onChange }: AthletePickerProps) {
  const [linkedName, setLinkedName] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Athlete[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!athleteId) {
      setLinkedName(null);
      return;
    }
    let cancelled = false;
    athletesApi
      .get(athleteId)
      .then((athlete) => {
        if (!cancelled) setLinkedName(`${athlete.first_name} ${athlete.last_name}`);
      })
      .catch(() => {
        if (!cancelled) setLinkedName(null);
      });
    return () => {
      cancelled = true;
    };
  }, [athleteId]);

  const search = async () => {
    setLoading(true);
    setError(null);
    try {
      const all = await athletesApi.list({ limit: 200 });
      const lower = query.trim().toLowerCase();
      setResults(
        lower
          ? all.filter((athlete) => `${athlete.first_name} ${athlete.last_name}`.toLowerCase().includes(lower))
          : all,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load the athlete roster.");
    } finally {
      setLoading(false);
    }
  };

  if (athleteId) {
    return (
      <div className="field">
        <Icon name="check" />
        <div className="fbody">
          <label>Roster athlete</label>
          <span>{linkedName ?? "Linked"}</span>
        </div>
        <button
          type="button"
          className="chip"
          onClick={() => {
            onChange("");
            setResults(null);
            setQuery("");
          }}
        >
          Unlink
        </button>
      </div>
    );
  }

  return (
    <div className="field" style={{ flexDirection: "column", alignItems: "stretch" }}>
      <div className="fbody">
        <label htmlFor="v2AthleteSearch">Roster athlete (optional)</label>
        <input
          id="v2AthleteSearch"
          placeholder="Search the roster by name"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void search();
          }}
        />
      </div>
      <button type="button" className="chip" onClick={() => void search()} disabled={loading} style={{ marginTop: 6 }}>
        {loading ? "Searching…" : "Search Roster"}
      </button>
      {error ? (
        <p className="card-note" style={{ color: "var(--fail)" }}>
          {error}
        </p>
      ) : null}
      {results ? (
        results.length > 0 ? (
          <div className="compact-list" style={{ marginTop: 6 }}>
            {results.map((athlete) => (
              <button
                type="button"
                key={athlete.id}
                className="compact-row"
                onClick={() => {
                  onChange(athlete.id);
                  setResults(null);
                  setQuery("");
                }}
              >
                <strong>
                  {athlete.first_name} {athlete.last_name}
                </strong>
                <span>{athlete.position}</span>
              </button>
            ))}
          </div>
        ) : (
          <p className="card-note">No athlete on the roster matches that search.</p>
        )
      ) : null}
    </div>
  );
}

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "@/api/client";
import { athletes as athletesApi } from "@/api/coachClient";
import type { Athlete } from "@/api/types";
import { Icon } from "@/components/IconSprite";

/**
 * The athlete-facing screens have no account system to say whose dashboard
 * this is (accounts are Phase 21, not built), so — same honest choice as the
 * coach Player Profile — the viewer picks an athlete from the real roster by
 * name rather than the screen guessing or inventing "you".
 */
export function SelectAthletePrompt({ note }: { note: string }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Athlete[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <>
      <p className="unavailable-note" role="note">
        <Icon name="clock" />
        <span>
          <b>No athlete selected.</b> {note}
        </span>
      </p>
      <div className="card">
        <h3>
          <Icon name="search" />
          Find Your Profile
        </h3>
        <div className="row2">
          <div className="field">
            <Icon name="search" />
            <div className="fbody">
              <label htmlFor="athlete-search">Search by name</label>
              <input
                id="athlete-search"
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void search();
                }}
                placeholder="e.g. Jordan Williams"
              />
            </div>
          </div>
          <button className="chip" type="button" onClick={() => void search()} disabled={loading}>
            {loading ? "Searching…" : "Search"}
          </button>
        </div>
        {error ? (
          <p className="card-note" style={{ color: "var(--fail)" }}>
            {error}
          </p>
        ) : null}
        {results ? (
          results.length > 0 ? (
            <div className="compact-list" style={{ marginTop: 10 }}>
              {results.map((athlete) => (
                <button
                  type="button"
                  key={athlete.id}
                  className="compact-row"
                  onClick={() => navigate(`?athleteId=${athlete.id}`, { replace: true })}
                >
                  <strong>
                    {athlete.first_name} {athlete.last_name}
                  </strong>
                  <span>{athlete.position}</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="card-note">No athlete profile matches that search.</p>
          )
        ) : null}
      </div>
    </>
  );
}

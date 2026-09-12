import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "@/api/client";
import { athletes as athletesApi } from "@/api/coachClient";
import { LEGACY_POSITIONS } from "@/api/types";
import type { Athlete, LegacyPosition } from "@/api/types";
import { Icon } from "@/components/IconSprite";
import { ViewHeader } from "@/components/chrome";

/**
 * Genesis Search — real, structured search over the actual roster.
 *
 * The wireframe's "Genesis" is a natural-language query box ("Show me South
 * Florida nickel defenders with elite TruStar fit"). There is no query
 * parser or athlete index behind that, and building one would mean either a
 * fake NLP demo or an unreviewed new backend service — neither is honest.
 * What's real and buildable today is a structured filter over
 * GET /api/v1/athletes, so that's what this is, labeled as such rather than
 * dressed up as natural language.
 */
export function GenesisSearchPage() {
  const [name, setName] = useState("");
  const [position, setPosition] = useState<LegacyPosition | "">("");
  const [gradYear, setGradYear] = useState("");
  const [minGpa, setMinGpa] = useState("");
  const [results, setResults] = useState<Athlete[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = async () => {
    setLoading(true);
    setError(null);
    try {
      const roster = await athletesApi.list({ position: position || undefined, limit: 200 });
      const lowerName = name.trim().toLowerCase();
      const year = gradYear.trim() ? Number(gradYear) : null;
      const gpa = minGpa.trim() ? Number(minGpa) : null;
      setResults(
        roster.filter((athlete) => {
          if (lowerName && !`${athlete.first_name} ${athlete.last_name}`.toLowerCase().includes(lowerName)) {
            return false;
          }
          if (year && athlete.grad_year !== year) return false;
          if (gpa != null && (athlete.gpa == null || athlete.gpa < gpa)) return false;
          return true;
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the TruGrade backend.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="view">
      <ViewHeader title={<span className="accent">GENESIS</span>} subtitle="Structured search over the real athlete roster." />
      <div className="vbody">
        <p className="unavailable-note" role="note">
          <Icon name="clock" />
          <span>
            <b>Not natural language yet.</b> Genesis is a filter over the real roster today — type a
            query like the wireframe's example and it won't be parsed. Structured filters below search
            real athletes.
          </span>
        </p>

        <div className="card">
          <h3>
            <Icon name="search" />
            Search the Roster
          </h3>
          <div className="row2">
            <div className="field">
              <Icon name="user" />
              <div className="fbody">
                <label htmlFor="genesis-name">Name</label>
                <input id="genesis-name" type="text" value={name} onChange={(event) => setName(event.target.value)} />
              </div>
            </div>
            <div className="field">
              <div className="fbody">
                <label htmlFor="genesis-position">Position</label>
                <select
                  id="genesis-position"
                  value={position}
                  onChange={(event) => setPosition(event.target.value as LegacyPosition | "")}
                >
                  <option value="">Any</option>
                  {LEGACY_POSITIONS.map((pos) => (
                    <option key={pos} value={pos}>
                      {pos}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
          <div className="row2" style={{ marginTop: 10 }}>
            <div className="field">
              <Icon name="calendar" />
              <div className="fbody">
                <label htmlFor="genesis-grad-year">Class Year</label>
                <input
                  id="genesis-grad-year"
                  type="number"
                  value={gradYear}
                  onChange={(event) => setGradYear(event.target.value)}
                  placeholder="e.g. 2027"
                />
              </div>
            </div>
            <div className="field">
              <Icon name="book" />
              <div className="fbody">
                <label htmlFor="genesis-gpa">Minimum GPA</label>
                <input
                  id="genesis-gpa"
                  type="number"
                  step="0.1"
                  value={minGpa}
                  onChange={(event) => setMinGpa(event.target.value)}
                  placeholder="e.g. 3.0"
                />
              </div>
            </div>
          </div>
          <button className="btn-solid" type="button" onClick={() => void search()} disabled={loading} style={{ marginTop: 12 }}>
            {loading ? "Searching…" : "Search Roster"}
          </button>
          {error ? (
            <p className="card-note" style={{ color: "var(--fail)" }}>
              {error}
            </p>
          ) : null}
        </div>

        {results ? (
          <div className="card">
            <h3>
              <Icon name="users" />
              Results ({results.length})
            </h3>
            {results.length > 0 ? (
              <div className="row-list">
                {results.map((athlete) => (
                  <div className="row-item" key={athlete.id}>
                    <div className="rl">
                      <Link to={`/coach/player-profile?athleteId=${athlete.id}`}>
                        {athlete.first_name} {athlete.last_name}
                      </Link>
                    </div>
                    <div className="rv">
                      {athlete.position}
                      {athlete.school ? ` · ${athlete.school}` : ""}
                      {athlete.grad_year ? ` · ${athlete.grad_year}` : ""}
                      {athlete.gpa != null ? ` · ${athlete.gpa.toFixed(1)} GPA` : ""}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="card-note">No athlete on the roster matches those filters.</p>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

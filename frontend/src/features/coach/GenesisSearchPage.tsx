import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, scout } from "@/api/client";
import { athletes as athletesApi } from "@/api/coachClient";
import { LEGACY_POSITIONS } from "@/api/types";
import type { Athlete, GenesisQueryResult, LegacyPosition } from "@/api/types";
import { Icon } from "@/components/IconSprite";
import { ViewHeader } from "@/components/chrome";

/**
 * Genesis Search — real natural-language search over the real roster.
 *
 * Gemini parses a free-text query (app/main.py's /api/v1/scout/genesis-query)
 * into the same structured fields the manual filters below use — position,
 * class year, hard metrics, academics, state, school, name. Never a black
 * box: the parsed interpretation and every filter it extracted are always
 * shown before results, and null means "not stated in the query," never a
 * guessed value. Results only ever come from the real roster; nothing here
 * is fabricated. The manual structured filters stay available underneath
 * for when a coach wants precise control or Genesis misreads something.
 */

/** True if every stated criterion in `q` matches this athlete. A criterion
 * the query didn't state (null/undefined) is skipped, never treated as a
 * failing match. */
function matchesGenesisCriteria(athlete: Athlete, q: GenesisQueryResult): boolean {
  if (q.position && athlete.position !== q.position) return false;
  if (q.grad_year_min != null && (athlete.grad_year == null || athlete.grad_year < q.grad_year_min)) return false;
  if (q.grad_year_max != null && (athlete.grad_year == null || athlete.grad_year > q.grad_year_max)) return false;
  if (q.height_in_min != null && (athlete.height_in == null || athlete.height_in < q.height_in_min)) return false;
  if (q.height_in_max != null && (athlete.height_in == null || athlete.height_in > q.height_in_max)) return false;
  if (q.weight_lbs_min != null && (athlete.weight_lbs == null || athlete.weight_lbs < q.weight_lbs_min)) return false;
  if (q.weight_lbs_max != null && (athlete.weight_lbs == null || athlete.weight_lbs > q.weight_lbs_max)) return false;
  if (q.forty_s_max != null && (athlete.forty_s == null || athlete.forty_s > q.forty_s_max)) return false;
  if (q.shuttle_s_max != null && (athlete.shuttle_s == null || athlete.shuttle_s > q.shuttle_s_max)) return false;
  if (q.bench_lbs_min != null && (athlete.bench_lbs == null || athlete.bench_lbs < q.bench_lbs_min)) return false;
  if (q.squat_lbs_min != null && (athlete.squat_lbs == null || athlete.squat_lbs < q.squat_lbs_min)) return false;
  if (q.gpa_min != null && (athlete.gpa == null || athlete.gpa < q.gpa_min)) return false;
  if (q.sat_min != null && (athlete.sat == null || athlete.sat < q.sat_min)) return false;
  if (q.act_min != null && (athlete.act == null || athlete.act < q.act_min)) return false;
  if (q.state && athlete.state?.toUpperCase() !== q.state.toUpperCase()) return false;
  if (q.school_contains && !athlete.school?.toLowerCase().includes(q.school_contains.toLowerCase())) return false;
  if (q.name_contains) {
    const full = `${athlete.first_name} ${athlete.last_name}`.toLowerCase();
    if (!full.includes(q.name_contains.toLowerCase())) return false;
  }
  return true;
}

/** Readable labels for whatever Genesis actually parsed out of the query —
 * only the criteria that were stated, so this list is never padded with
 * "not specified" noise. */
function parsedFilterChips(q: GenesisQueryResult): string[] {
  const chips: string[] = [];
  if (q.position) chips.push(`Position: ${q.position}`);
  if (q.grad_year_min != null || q.grad_year_max != null) {
    chips.push(
      q.grad_year_min != null && q.grad_year_max != null && q.grad_year_min === q.grad_year_max
        ? `Class of ${q.grad_year_min}`
        : `Class year: ${q.grad_year_min ?? "any"}–${q.grad_year_max ?? "any"}`,
    );
  }
  if (q.height_in_min != null || q.height_in_max != null) {
    chips.push(`Height: ${q.height_in_min ?? "any"}–${q.height_in_max ?? "any"} in`);
  }
  if (q.weight_lbs_min != null || q.weight_lbs_max != null) {
    chips.push(`Weight: ${q.weight_lbs_min ?? "any"}–${q.weight_lbs_max ?? "any"} lbs`);
  }
  if (q.forty_s_max != null) chips.push(`40-yd ≤ ${q.forty_s_max}s`);
  if (q.shuttle_s_max != null) chips.push(`Shuttle ≤ ${q.shuttle_s_max}s`);
  if (q.bench_lbs_min != null) chips.push(`Bench ≥ ${q.bench_lbs_min} lbs`);
  if (q.squat_lbs_min != null) chips.push(`Squat ≥ ${q.squat_lbs_min} lbs`);
  if (q.gpa_min != null) chips.push(`GPA ≥ ${q.gpa_min}`);
  if (q.sat_min != null) chips.push(`SAT ≥ ${q.sat_min}`);
  if (q.act_min != null) chips.push(`ACT ≥ ${q.act_min}`);
  if (q.state) chips.push(`State: ${q.state}`);
  if (q.school_contains) chips.push(`School: "${q.school_contains}"`);
  if (q.name_contains) chips.push(`Name: "${q.name_contains}"`);
  return chips;
}

function ResultsList({ results }: { results: Athlete[] }) {
  return results.length > 0 ? (
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
  );
}

export function GenesisSearchPage() {
  const [nlQuery, setNlQuery] = useState("");
  const [nlLoading, setNlLoading] = useState(false);
  const [nlError, setNlError] = useState<string | null>(null);
  const [nlParsed, setNlParsed] = useState<GenesisQueryResult | null>(null);
  const [nlResults, setNlResults] = useState<Athlete[] | null>(null);

  const [name, setName] = useState("");
  const [position, setPosition] = useState<LegacyPosition | "">("");
  const [gradYear, setGradYear] = useState("");
  const [minGpa, setMinGpa] = useState("");
  const [results, setResults] = useState<Athlete[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const searchByLanguage = async () => {
    if (!nlQuery.trim()) return;
    setNlLoading(true);
    setNlError(null);
    try {
      const parsed = await scout.genesisQuery({ query: nlQuery });
      setNlParsed(parsed);
      const validPosition = LEGACY_POSITIONS.includes(parsed.position as LegacyPosition)
        ? (parsed.position as LegacyPosition)
        : undefined;
      const roster = await athletesApi.list({ position: validPosition, limit: 200 });
      setNlResults(roster.filter((athlete) => matchesGenesisCriteria(athlete, parsed)));
    } catch (err) {
      setNlError(err instanceof ApiError ? err.message : "Could not reach the TruGrade backend.");
      setNlParsed(null);
      setNlResults(null);
    } finally {
      setNlLoading(false);
    }
  };

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
      <ViewHeader title={<span className="accent">GENESIS</span>} subtitle="Natural-language and structured search over the real athlete roster." />
      <div className="vbody">
        <div className="card">
          <h3>
            <Icon name="brain" />
            Ask Genesis
          </h3>
          <div className="field">
            <Icon name="search" />
            <div className="fbody">
              <label htmlFor="genesis-nl-query">Describe who you're looking for</label>
              <input
                id="genesis-nl-query"
                type="text"
                value={nlQuery}
                onChange={(event) => setNlQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void searchByLanguage();
                }}
                placeholder="e.g. offensive linemen over 300 lbs with a 3.0 GPA"
              />
            </div>
          </div>
          <button className="btn-solid" type="button" onClick={() => void searchByLanguage()} disabled={nlLoading || !nlQuery.trim()} style={{ marginTop: 12 }}>
            {nlLoading ? "Parsing…" : "Search"}
          </button>
          {nlError ? (
            <p className="card-note" style={{ color: "var(--fail)" }}>
              {nlError}
            </p>
          ) : null}
          {nlParsed ? (
            <div style={{ marginTop: 14 }}>
              <p className="card-note">
                <Icon name="check" className="sm" /> {nlParsed.interpretation_note}
              </p>
              {parsedFilterChips(nlParsed).length > 0 ? (
                <div className="presets" style={{ marginTop: 8 }}>
                  {parsedFilterChips(nlParsed).map((chip) => (
                    <span className="chip" key={chip} style={{ cursor: "default" }}>
                      {chip}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="card-note">No specific filters were found in that query — showing every athlete.</p>
              )}
            </div>
          ) : null}
        </div>

        {nlResults ? (
          <div className="card">
            <h3>
              <Icon name="users" />
              Genesis Results ({nlResults.length})
            </h3>
            <ResultsList results={nlResults} />
          </div>
        ) : null}

        <div className="card">
          <h3>
            <Icon name="search" />
            Structured Filters
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
            <ResultsList results={results} />
          </div>
        ) : null}
      </div>
    </div>
  );
}

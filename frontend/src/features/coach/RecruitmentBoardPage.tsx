import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "@/api/client";
import { athletes as athletesApi, board as boardApi } from "@/api/coachClient";
import { BOARD_STAGES, BOARD_STAGE_LABELS } from "@/api/types";
import type { Athlete, BoardEntry, BoardStage } from "@/api/types";
import { Icon } from "@/components/IconSprite";
import { ViewHeader } from "@/components/chrome";

const STAGE_ICON: Record<BoardStage, "star" | "target" | "shield" | "chart" | "check"> = {
  watchlist: "star",
  evaluating: "target",
  offer_board: "shield",
  development: "chart",
  follow_up: "check",
};

/** Recruitment Board — real entries from GET/PUT/DELETE /api/v1/board. */
export function RecruitmentBoardPage() {
  const [entries, setEntries] = useState<BoardEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    boardApi
      .list()
      .then((result) => setEntries(result))
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Could not reach the TruGrade backend."),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const byStage = useMemo(() => {
    const grouped = new Map<BoardStage, BoardEntry[]>(BOARD_STAGES.map((stage) => [stage, []]));
    for (const entry of entries ?? []) {
      grouped.get(entry.stage)?.push(entry);
    }
    return grouped;
  }, [entries]);

  const moveStage = async (athleteId: string, stage: BoardStage, notes?: string | null) => {
    await boardApi.upsert(athleteId, { stage, notes });
    load();
  };

  const remove = async (athleteId: string) => {
    await boardApi.remove(athleteId);
    load();
  };

  return (
    <div className="view">
      <ViewHeader
        title={
          <>
            COACH RECRUITMENT <span className="accent">BOARD</span>
          </>
        }
        subtitle="Build. Evaluate. Develop. Recruit."
      />
      <div className="vbody">
        {error ? (
          <p className="unavailable-note" role="alert">
            <Icon name="x" />
            <span>{error}</span>
          </p>
        ) : null}

        <AddToBoardCard onAdded={load} />

        {/* Five stages, not the four the shared .cards-4 grid assumes — override
            the column count only, so a fifth column doesn't wrap onto its own row. */}
        <div className="cards-4" style={{ gridTemplateColumns: "repeat(5, 1fr)" }}>
          {BOARD_STAGES.map((stage) => {
            const stageEntries = byStage.get(stage) ?? [];
            return (
              <div className="card" key={stage}>
                <h3>
                  <Icon name={STAGE_ICON[stage]} />
                  {BOARD_STAGE_LABELS[stage]}
                </h3>
                <p className="card-note">
                  {loading ? "Loading…" : `${stageEntries.length} athlete${stageEntries.length === 1 ? "" : "s"}`}
                </p>
                <div className="compact-list" style={{ marginTop: 8 }}>
                  {stageEntries.map((entry) => (
                    <div className="compact-row" key={entry.athlete_id} style={{ cursor: "default" }}>
                      <span style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
                        <Link to={`/coach/player-profile?athleteId=${entry.athlete_id}`}>
                          <strong>
                            {entry.first_name ?? "—"} {entry.last_name ?? ""}
                          </strong>
                        </Link>
                        <span>{entry.position ?? "—"}</span>
                      </span>
                      <span style={{ display: "flex", flexDirection: "column", gap: 4, alignItems: "flex-end" }}>
                        <select
                          aria-label={`Move ${entry.first_name ?? "athlete"} ${entry.last_name ?? ""}`}
                          value={entry.stage}
                          onChange={(event) => void moveStage(entry.athlete_id, event.target.value as BoardStage, entry.notes)}
                        >
                          {BOARD_STAGES.map((option) => (
                            <option key={option} value={option}>
                              {BOARD_STAGE_LABELS[option]}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          className="chip"
                          onClick={() => void remove(entry.athlete_id)}
                          aria-label={`Remove ${entry.first_name ?? "athlete"} ${entry.last_name ?? ""} from the board`}
                        >
                          <Icon name="x" /> Remove
                        </button>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

interface AddToBoardCardProps {
  onAdded: () => void;
}

function AddToBoardCard({ onAdded }: AddToBoardCardProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Athlete[] | null>(null);
  const [selected, setSelected] = useState<Athlete | null>(null);
  const [stage, setStage] = useState<BoardStage>("watchlist");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
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

  const add = async () => {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      await boardApi.upsert(selected.id, { stage });
      setSelected(null);
      setResults(null);
      setQuery("");
      onAdded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add that athlete to the board.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card">
      <h3>
        <Icon name="search" />
        Add an Athlete to the Board
      </h3>
      <div className="row2">
        <div className="field">
          <Icon name="search" />
          <div className="fbody">
            <label htmlFor="board-search">Search the roster by name</label>
            <input
              id="board-search"
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
          {loading ? "Searching…" : "Search Roster"}
        </button>
      </div>

      {results ? (
        results.length > 0 ? (
          <div className="compact-list" style={{ marginTop: 10 }}>
            {results.map((athlete) => (
              <button
                type="button"
                key={athlete.id}
                className={selected?.id === athlete.id ? "compact-row selected" : "compact-row"}
                onClick={() => setSelected(athlete)}
                aria-pressed={selected?.id === athlete.id}
              >
                <strong>
                  {athlete.first_name} {athlete.last_name}
                </strong>
                <span>{athlete.position}</span>
              </button>
            ))}
          </div>
        ) : (
          <p className="card-note">No athletes on the roster match that search.</p>
        )
      ) : null}

      {selected ? (
        <div className="row2" style={{ marginTop: 10, alignItems: "center" }}>
          <div className="field">
            <div className="fbody">
              <label htmlFor="board-stage">
                Add {selected.first_name} {selected.last_name} to
              </label>
              <select id="board-stage" value={stage} onChange={(event) => setStage(event.target.value as BoardStage)}>
                {BOARD_STAGES.map((option) => (
                  <option key={option} value={option}>
                    {BOARD_STAGE_LABELS[option]}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <button className="btn-solid" type="button" onClick={() => void add()} disabled={saving}>
            {saving ? "Adding…" : "Add to Board"}
          </button>
        </div>
      ) : null}

      {error ? (
        <p className="card-note" style={{ color: "var(--fail)" }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

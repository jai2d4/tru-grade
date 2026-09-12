import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { coachDashboard, teamNeeds as teamNeedsApi } from "@/api/coachClient";
import { ApiError } from "@/api/client";
import { BOARD_STAGES, BOARD_STAGE_LABELS, LEGACY_POSITIONS } from "@/api/types";
import type { CoachDashboard, LegacyPosition } from "@/api/types";
import { Icon } from "@/components/IconSprite";
import { ViewHeader } from "@/components/chrome";

/**
 * Coach Dashboard — real counts from GET /api/v1/coach/dashboard, plus an
 * inline Team Needs editor (the only screen the original wireframe put that
 * card on). Recruiting Board and Player Profile are their own routes.
 */
export function CoachDashboardPage() {
  const [data, setData] = useState<CoachDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    coachDashboard
      .get()
      .then((result) => setData(result))
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Could not reach the TruGrade backend."),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onBoard = data ? BOARD_STAGES.reduce((sum, stage) => sum + (data.board_counts[stage] ?? 0), 0) : null;

  return (
    <div className="view">
      <ViewHeader
        title={
          <>
            COLLEGE COACH <span className="accent">DASHBOARD</span>
          </>
        }
        subtitle="Recruit. Evaluate. Win."
      />
      <div className="vbody">
        {error ? (
          <p className="unavailable-note" role="alert">
            <Icon name="x" />
            <span>{error}</span>
          </p>
        ) : null}

        <div className="cards-4">
          {[
            { label: "Total Athletes", icon: "users" as const, value: data?.total_athletes },
            { label: "Truth Reports Run", icon: "shield" as const, value: data?.total_evaluations },
            { label: "On the Board", icon: "star" as const, value: onBoard },
            { label: "Offer Board", icon: "target" as const, value: data?.board_counts.offer_board },
          ].map((tile) => (
            <div className="stat-tile" key={tile.label}>
              <Icon name={tile.icon} className="sm" />
              <div className="stat-label">{tile.label}</div>
              <div className="stat-val" style={{ opacity: tile.value == null ? 0.5 : 1 }}>
                {loading ? "…" : (tile.value ?? "—")}
              </div>
            </div>
          ))}
        </div>

        <div className="cards-2">
          <div className="card">
            <h3>
              <Icon name="users" />
              Recruiting Board
            </h3>
            <div className="row-list">
              {BOARD_STAGES.map((stage) => (
                <div className="row-item" key={stage}>
                  <div className="rl">{BOARD_STAGE_LABELS[stage]}</div>
                  <div className="rv">{loading ? "…" : (data?.board_counts[stage] ?? 0)}</div>
                </div>
              ))}
            </div>
            <Link className="chip" to="/coach/board" style={{ display: "inline-block", marginTop: 12 }}>
              Open Recruitment Board
            </Link>
          </div>

          <TeamNeedsCard needs={data?.team_needs ?? []} onSaved={load} />
        </div>

        <div className="card">
          <h3>
            <Icon name="shield" />
            Recent Truth Reports
          </h3>
          {loading ? (
            <p className="card-note">Loading…</p>
          ) : data && data.recent_evaluations.length > 0 ? (
            <div className="row-list">
              {data.recent_evaluations.map((evaluation) => (
                <div className="row-item" key={evaluation.id}>
                  <div className="rl">
                    {evaluation.position_evaluated}
                    {evaluation.is_game_changer ? " · Game Changer" : ""}
                  </div>
                  <div className="rv">
                    {evaluation.projected_tier ?? "Unranked"} ·{" "}
                    {new Date(evaluation.created_at).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="card-note">No Truth Reports have been run yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}

interface TeamNeedsCardProps {
  needs: { position: LegacyPosition; priority: number }[];
  onSaved: () => void;
}

function TeamNeedsCard({ needs, onSaved }: TeamNeedsCardProps) {
  const [position, setPosition] = useState<LegacyPosition>("QB");
  const [priority, setPriority] = useState(3);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const byPosition = new Map(needs.map((need) => [need.position, need.priority]));

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      await teamNeedsApi.set(position, priority);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save that team need.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card">
      <h3>
        <Icon name="target" />
        Team Needs
      </h3>
      <div className="row-list">
        {LEGACY_POSITIONS.map((pos) => (
          <div className="row-item" key={pos}>
            <div className="rl">{pos}</div>
            <div className="rv">{byPosition.has(pos) ? `Priority ${byPosition.get(pos)}` : "Not set"}</div>
          </div>
        ))}
      </div>
      <div className="row2" style={{ marginTop: 10 }}>
        <div className="field">
          <div className="fbody">
            <label htmlFor="team-need-position">Position</label>
            <select
              id="team-need-position"
              value={position}
              onChange={(event) => setPosition(event.target.value as LegacyPosition)}
            >
              {LEGACY_POSITIONS.map((pos) => (
                <option key={pos} value={pos}>
                  {pos}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="field">
          <div className="fbody">
            <label htmlFor="team-need-priority">Priority (1 highest)</label>
            <select
              id="team-need-priority"
              value={priority}
              onChange={(event) => setPriority(Number(event.target.value))}
            >
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
      <button className="chip" type="button" onClick={submit} disabled={saving} style={{ marginTop: 10 }}>
        {saving ? "Saving…" : "Set Need"}
      </button>
      {error ? (
        <p className="card-note" style={{ color: "var(--fail)" }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

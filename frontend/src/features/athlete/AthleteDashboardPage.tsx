import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { athletes as athletesApi } from "@/api/coachClient";
import type { FilmLink } from "@/api/types";
import { Icon } from "@/components/IconSprite";
import { ViewHeader } from "@/components/chrome";
import { SelectAthletePrompt } from "./SelectAthletePrompt";
import { useEvaluations } from "./useEvaluations";

/** Athlete Dashboard — real Truth Report history for a chosen athlete. */
export function AthleteDashboardPage() {
  const [searchParams] = useSearchParams();
  const athleteId = searchParams.get("athleteId");

  return (
    <div className="view">
      <ViewHeader
        title={
          <>
            ATHLETE <span className="accent">DASHBOARD</span>
          </>
        }
        subtitle="Overview • Analyze • Elevate"
      />
      <div className="vbody">
        {athleteId ? (
          <Loaded athleteId={athleteId} />
        ) : (
          <SelectAthletePrompt note="Find your profile below to see your Truth Report history." />
        )}
      </div>
    </div>
  );
}

function Loaded({ athleteId }: { athleteId: string }) {
  const { athlete, evaluationList, error, loading } = useEvaluations(athleteId, null);
  const [filmLinks, setFilmLinks] = useState<FilmLink[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    athletesApi
      .filmLinks(athleteId)
      .then((links) => {
        if (!cancelled) setFilmLinks(links);
      })
      .catch(() => {
        if (!cancelled) setFilmLinks([]);
      });
    return () => {
      cancelled = true;
    };
  }, [athleteId]);

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

  const latest = evaluationList[0] ?? null;

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

      <div className="cards-3">
        <div className="card">
          <h3>
            <Icon name="shield" />
            Truth Reports on File
          </h3>
          <div className="stat-val" style={{ fontSize: 22 }}>
            {evaluationList.length}
          </div>
        </div>
        <div className="card">
          <h3>
            <Icon name="target" />
            Latest Projected Tier
          </h3>
          <div className="stat-val" style={{ fontSize: 22, opacity: latest?.projected_tier ? 1 : 0.5 }}>
            {latest?.projected_tier?.replaceAll("_", " ") ?? "—"}
          </div>
        </div>
        <div className="card">
          <h3>
            <Icon name="bolt" />
            Game-Changer Flag
          </h3>
          <div className="stat-val" style={{ fontSize: 22 }}>
            {latest ? (latest.is_game_changer ? "Yes" : "No") : "—"}
          </div>
        </div>
      </div>

      <div className="card">
        <h3>
          <Icon name="shield" />
          Truth Report History
        </h3>
        {evaluationList.length > 0 ? (
          <div className="row-list">
            {evaluationList.map((evaluation) => (
              <div className="row-item" key={evaluation.id}>
                <div className="rl">
                  {evaluation.position_evaluated} · {new Date(evaluation.created_at).toLocaleDateString()}
                </div>
                <div className="rv" style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <span>{evaluation.projected_tier?.replaceAll("_", " ") ?? "Unranked"}</span>
                  <Link to={`/athlete/film-report?athleteId=${athleteId}&evaluationId=${evaluation.id}`}>
                    Film Report
                  </Link>
                  <Link to={`/athlete/traits?athleteId=${athleteId}&evaluationId=${evaluation.id}`}>
                    Traits
                  </Link>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="card-note">No Truth Reports have been run for this athlete yet.</p>
        )}
      </div>

      <div className="card">
        <h3>
          <Icon name="film" />
          Linked Film
        </h3>
        {filmLinks === null ? (
          <p className="card-note">Loading…</p>
        ) : filmLinks.length > 0 ? (
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
            No film linked yet — a coach links film through the Film Analysis workspace.
          </p>
        )}
      </div>
    </>
  );
}

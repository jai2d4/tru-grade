import { useSearchParams } from "react-router-dom";
import { rankLabel } from "@/lib/makeupGrade";
import { Icon } from "@/components/IconSprite";
import { ViewHeader } from "@/components/chrome";
import { SelectAthletePrompt } from "./SelectAthletePrompt";
import { useEvaluations } from "./useEvaluations";

/** AI Film Report — the film grades and flags from a real, stored Truth Report. */
export function AiFilmReportPage() {
  const [searchParams] = useSearchParams();
  const athleteId = searchParams.get("athleteId");
  const evaluationId = searchParams.get("evaluationId");

  return (
    <div className="view">
      <ViewHeader
        title={
          <>
            AI FILM <span className="accent">REPORT</span>
          </>
        }
        subtitle="Film grades and flags from a graded Truth Report."
      />
      <div className="vbody">
        {athleteId ? (
          <Loaded athleteId={athleteId} evaluationId={evaluationId} />
        ) : (
          <SelectAthletePrompt note="Find your profile to see film grades from your Truth Reports." />
        )}
      </div>
    </div>
  );
}

function Loaded({ athleteId, evaluationId }: { athleteId: string; evaluationId: string | null }) {
  const { selected, evaluationList, error, loading } = useEvaluations(athleteId, evaluationId);

  if (error) {
    return (
      <p className="unavailable-note" role="alert">
        <Icon name="x" />
        <span>{error}</span>
      </p>
    );
  }
  if (loading) {
    return <p className="card-note">Loading…</p>;
  }
  if (evaluationList.length === 0) {
    return <p className="card-note">No Truth Reports have been run for this athlete yet.</p>;
  }
  if (!selected) {
    return <p className="card-note">That Truth Report could not be found.</p>;
  }

  const grades = Object.entries(selected.film_grades ?? {});
  const flags = selected.film_flags ?? [];

  return (
    <>
      <div className="card">
        <p className="card-note" style={{ margin: 0 }}>
          From the {selected.position_evaluated} Truth Report run on{" "}
          {new Date(selected.created_at).toLocaleDateString()}
          {evaluationList.length > 1 ? ` · ${evaluationList.length} reports on file` : ""}
        </p>
        {selected.identification_note ? (
          <p
            className="tier-sub"
            style={{ marginTop: 8, color: selected.player_identified === false ? "var(--fail)" : "var(--dim)" }}
          >
            {selected.player_identified === false ? (
              <>
                <Icon name="x" /> PLAYER NOT IDENTIFIED —{" "}
              </>
            ) : (
              <>
                <Icon name="check" />{" "}
              </>
            )}
            {selected.identification_note}
          </p>
        ) : null}
      </div>

      <div className="card">
        <h3>
          <Icon name="film" />
          Film Grades
        </h3>
        {grades.length > 0 ? (
          <div className="stat-grid">
            {grades.map(([factor, rank]) => (
              <div
                className={rank === "GAME_CHANGER" ? "stat-tile gc" : rank === "NGE" ? "stat-tile nge" : "stat-tile"}
                key={factor}
              >
                <Icon name="bolt" className="sm" />
                <div className="stat-label">{factor}</div>
                <div className="stat-val">{rankLabel(String(rank))}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="card-note">No film grades were recorded on this report.</p>
        )}
      </div>

      <div className="card">
        <h3>
          <Icon name="flag" />
          Flags
        </h3>
        {flags.length > 0 ? (
          flags.map((flag, index) => (
            <div className="gc" style={{ marginTop: index === 0 ? 0 : 10 }} key={`${flag}-${index}`}>
              <p style={{ margin: 0 }}>{flag}</p>
            </div>
          ))
        ) : (
          <p className="card-note">No Game-Changer or NGE-level flags on this film.</p>
        )}
      </div>
    </>
  );
}

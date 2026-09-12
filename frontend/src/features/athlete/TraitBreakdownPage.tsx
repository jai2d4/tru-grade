import { useSearchParams } from "react-router-dom";
import { rankLabel } from "@/lib/makeupGrade";
import { Icon } from "@/components/IconSprite";
import { ViewHeader } from "@/components/chrome";
import { SelectAthletePrompt } from "./SelectAthletePrompt";
import { useEvaluations } from "./useEvaluations";

export const GRADE_DOWN_ROWS: { key: "overall" | "p4" | "group_of_5" | "fcs" | "d2_d3_naia_juco"; label: string }[] = [
  { key: "overall", label: "Overall" },
  { key: "p4", label: "Power 4" },
  { key: "group_of_5", label: "Group of 5" },
  { key: "fcs", label: "FCS" },
  { key: "d2_d3_naia_juco", label: "D2 / D3 / NAIA / JUCO" },
];

/** Trait Breakdown — the hard-metric sieve and Profile & Makeup grade-down from a real Truth Report. */
export function TraitBreakdownPage() {
  const [searchParams] = useSearchParams();
  const athleteId = searchParams.get("athleteId");
  const evaluationId = searchParams.get("evaluationId");

  return (
    <div className="view">
      <ViewHeader
        title={
          <>
            TRAIT <span className="accent">BREAKDOWN</span>
          </>
        }
        subtitle="Hard metrics and Profile & Makeup grading from a graded Truth Report."
      />
      <div className="vbody">
        {athleteId ? (
          <Loaded athleteId={athleteId} evaluationId={evaluationId} />
        ) : (
          <SelectAthletePrompt note="Find your profile to see the trait breakdown from your Truth Reports." />
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

  const checks = selected.metric_sieve_results?.checks ?? [];
  const gradeDown = selected.makeup_grade_down;

  return (
    <>
      <p className="card-note">
        From the {selected.position_evaluated} Truth Report run on{" "}
        {new Date(selected.created_at).toLocaleDateString()}
        {evaluationList.length > 1 ? ` · ${evaluationList.length} reports on file` : ""}
      </p>

      <div className="card">
        <h3>
          <Icon name="ruler" />
          Hard Metrics
        </h3>
        {checks.length > 0 ? (
          <table>
            <tbody>
              <tr>
                <th>Metric</th>
                <th>Value</th>
                <th>Threshold</th>
                <th>Sieve</th>
              </tr>
              {checks.map((check) => (
                <tr key={check.metric}>
                  <td>{check.metric.replaceAll("_", " ")}</td>
                  <td className="val">{check.athlete_value ?? "—"}</td>
                  <td style={{ color: "var(--dim)", fontFamily: "IBM Plex Mono", fontSize: 12 }}>
                    {check.threshold}
                  </td>
                  <td>
                    {check.passed === true ? (
                      <span className="pill pass">
                        <Icon name="check" />
                        PASS
                      </span>
                    ) : check.passed === false ? (
                      <span className="pill fail">
                        <Icon name="x" />
                        FAIL
                      </span>
                    ) : (
                      <span className="pill na">NO DATA</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="card-note">No hard-metric sieve was recorded on this report.</p>
        )}
      </div>

      <div className="card">
        <h3>
          <Icon name="star" />
          Profile &amp; Makeup Grade-Down
        </h3>
        {gradeDown ? (
          <div className="row-list">
            {GRADE_DOWN_ROWS.map((row) => (
              <div className="row-item" key={row.key}>
                <div className="rl">{row.label}</div>
                <div className="rv">{rankLabel(gradeDown[row.key])}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="card-note">No Profile &amp; Makeup grade was recorded on this report.</p>
        )}
      </div>
    </>
  );
}

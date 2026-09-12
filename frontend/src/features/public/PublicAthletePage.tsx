import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { publicAthletes } from "@/api/coachClient";
import type { PublicAthlete } from "@/api/types";
import { Icon, IconSprite } from "@/components/IconSprite";
import { Stars } from "@/components/chrome";
import { tierStars } from "@/lib/metricSieve";

/**
 * The anonymous landing page a share-link token resolves to — deliberately
 * outside AppShell/the sidebar (see App.tsx): a recruiter or family member
 * opening this link has no TruGrade account and shouldn't see the coach nav.
 *
 * Scope is exactly what the /api/v1/public/athletes/{token} endpoint
 * returns: name, position, school, class year, and the real TRUSTAR
 * tier/rating. No hard metrics, coach notes, fit scores, or film — see
 * app/routers/public.py for what's deliberately left out and why.
 */
export function PublicAthletePage() {
  const { token } = useParams<{ token: string }>();
  const [athlete, setAthlete] = useState<PublicAthlete | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setError("This link is missing its share token.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    publicAthletes
      .get(token)
      .then(setAthlete)
      .catch((err: unknown) => {
        setError(
          err instanceof ApiError && err.status === 404
            ? "This link is invalid or has been revoked."
            : "Could not reach the TruGrade backend.",
        );
      })
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="public-rating-page">
      <IconSprite />
      <div className="public-rating-card">
        <div className="brand" style={{ marginBottom: 24 }}>
          <img className="brand-mark" src="/trugrade-mark.jpg" alt="TruGrade" />
          <div className="brand-txt">
            <span className="brand-word">
              <span className="tru">Tru</span>
              <span className="grade">Grade</span>
            </span>
            <span className="brand-sub">AI Truth Engine for Football Evaluation</span>
          </div>
        </div>

        {loading ? <p className="card-note">Loading…</p> : null}
        {error ? (
          <p className="unavailable-note" role="alert">
            <Icon name="x" />
            <span>{error}</span>
          </p>
        ) : null}

        {!loading && !error && athlete ? (
          <>
            <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
              <div className="avatar-ring" style={{ width: 64, height: 64 }}>
                <svg className="ic" style={{ width: 28, height: 28 }} aria-hidden="true">
                  <use href="#ic-user" />
                </svg>
              </div>
              <div>
                <h1 style={{ margin: 0 }}>
                  {athlete.first_name} {athlete.last_name}
                </h1>
                <p className="card-note" style={{ margin: 0 }}>
                  {athlete.position}
                  {athlete.school ? ` · ${athlete.school}` : ""}
                  {athlete.grad_year ? ` · Class of ${athlete.grad_year}` : ""}
                </p>
              </div>
            </div>

            <div className="rating-card" style={{ marginTop: 20 }}>
              <div className="rating-label">TRUSTAR RATING</div>
              <Stars
                count={tierStars({ tier: athlete.projected_tier ?? "UNRANKED", is_game_changer: athlete.is_game_changer })}
                label={
                  athlete.projected_tier
                    ? `Projected tier ${athlete.projected_tier.replaceAll("_", " ")}`
                    : "Not yet rated"
                }
              />
              <p className="card-note">
                {athlete.projected_tier
                  ? athlete.is_game_changer
                    ? "Flagged as a Game Changer on the most recent Truth Report."
                    : "Based on the most recent verified Truth Report."
                  : "No Truth Report has been run for this athlete yet."}
              </p>
            </div>

            <p className="card-note" style={{ marginTop: 20 }}>
              This is a verified, coach-shared summary. Full evaluations — hard metrics, film, and
              coach notes — stay private to the program.
            </p>
          </>
        ) : null}
      </div>
    </div>
  );
}

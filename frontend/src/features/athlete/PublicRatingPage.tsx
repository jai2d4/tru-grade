import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/api/client";
import { shareLinks as shareLinksApi } from "@/api/coachClient";
import type { ShareLink } from "@/api/types";
import { Icon } from "@/components/IconSprite";
import { Stars, ViewHeader } from "@/components/chrome";
import { tierStars } from "@/lib/metricSieve";
import { SelectAthletePrompt } from "./SelectAthletePrompt";
import { useEffectiveAthleteId } from "./useEffectiveAthleteId";
import { useEvaluations } from "./useEvaluations";

/**
 * Public Rating — lets an athlete (or their coach) generate a share-link
 * URL that shows only the basics + verified TRUSTAR tier to an anonymous
 * viewer (see app/routers/public.py and features/public/PublicAthletePage).
 * The rating shown here is the same real, verified TRUSTAR rating every
 * other screen reads — no separate "public" number is computed.
 */
export function PublicRatingPage() {
  const athleteId = useEffectiveAthleteId();

  return (
    <div className="view">
      <ViewHeader
        title={
          <>
            PUBLIC ATHLETE <span className="accent">RATING</span>
          </>
        }
        subtitle="Shareable. Verified. Recruit-ready."
      />
      <div className="vbody">
        {athleteId ? (
          <Loaded athleteId={athleteId} />
        ) : (
          <SelectAthletePrompt note="Find your profile below to generate a shareable rating link." />
        )}
      </div>
    </div>
  );
}

function Loaded({ athleteId }: { athleteId: string }) {
  const { athlete, evaluationList, error, loading } = useEvaluations(athleteId, null);
  const [link, setLink] = useState<ShareLink | null | undefined>(undefined);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const loadLink = useCallback(() => {
    shareLinksApi
      .get(athleteId)
      .then(setLink)
      .catch(() => setLink(null));
  }, [athleteId]);

  useEffect(() => {
    loadLink();
  }, [loadLink]);

  const publicUrl = link ? `${window.location.origin}/public/${link.token}` : null;

  const generate = async () => {
    setBusy(true);
    setLinkError(null);
    setCopied(false);
    try {
      const created = await shareLinksApi.create(athleteId);
      setLink(created);
    } catch (err) {
      setLinkError(err instanceof ApiError ? err.message : "Could not reach the TruGrade backend.");
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    setBusy(true);
    setLinkError(null);
    try {
      await shareLinksApi.revoke(athleteId);
      setLink(null);
      setCopied(false);
    } catch (err) {
      setLinkError(err instanceof ApiError ? err.message : "Could not reach the TruGrade backend.");
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    if (!publicUrl) return;
    try {
      await navigator.clipboard.writeText(publicUrl);
      setCopied(true);
    } catch {
      setLinkError("Could not copy — select and copy the link manually.");
    }
  };

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
  const sieve = latest?.metric_sieve_results ?? null;

  return (
    <div className="cards-2">
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
        <div className="rating-card" style={{ marginTop: 16 }}>
          <div className="rating-label">TRUSTAR RATING</div>
          {sieve ? (
            <Stars count={tierStars(sieve)} label={`Projected tier ${sieve.tier.replaceAll("_", " ")}`} />
          ) : (
            <Stars count={0} label="Not yet rated" />
          )}
          <p className="card-note">
            This is exactly what a public viewer will see — the same verified rating, nothing extra.
          </p>
        </div>
      </div>

      <div className="card">
        <h3>
          <Icon name="link" />
          Share Link
        </h3>
        {link === undefined ? (
          <p className="card-note">Loading…</p>
        ) : link ? (
          <>
            <div className="field" style={{ marginBottom: 10 }}>
              <Icon name="link" />
              <div className="fbody">
                <label htmlFor="share-link-url">Public link</label>
                <input id="share-link-url" type="text" readOnly value={publicUrl ?? ""} onFocus={(event) => event.currentTarget.select()} />
              </div>
            </div>
            <div className="presets">
              <button className="chip" type="button" onClick={() => void copy()} disabled={busy}>
                {copied ? "Copied!" : "Copy Link"}
              </button>
              <button className="chip" type="button" onClick={() => void generate()} disabled={busy}>
                Regenerate
              </button>
              <button className="chip" type="button" onClick={() => void revoke()} disabled={busy} style={{ color: "var(--fail)" }}>
                Revoke
              </button>
            </div>
            <p className="card-note" style={{ marginTop: 10 }}>
              Anyone with this link can view the basics and rating above — no login required.
              Regenerating replaces it; the old link stops working immediately.
            </p>
          </>
        ) : (
          <>
            <p className="card-note">
              No share link has been generated yet. Create one to give recruiters, family, or anyone
              else a public, verified view of name, position, school, class year, and TRUSTAR rating.
            </p>
            <button className="btn-solid" type="button" onClick={() => void generate()} disabled={busy}>
              {busy ? "Generating…" : "Generate Share Link"}
            </button>
          </>
        )}
        {linkError ? (
          <p className="card-note" style={{ color: "var(--fail)", marginTop: 10 }}>
            {linkError}
          </p>
        ) : null}
      </div>
    </div>
  );
}

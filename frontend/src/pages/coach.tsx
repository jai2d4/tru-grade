import { Icon } from "@/components/IconSprite";
import { Stars } from "@/components/chrome";
import { UnavailableView } from "@/components/UnavailableView";

/**
 * Coach-facing screens still without a real backend behind them.
 *
 * Coach Dashboard, Recruitment Board, Player Profile, and Genesis Search
 * moved to @/features/coach — they read and write real endpoints. Coach 360
 * Report stays here: it needs an AI reasoning pipeline that doesn't exist.
 */

export function Coach360ReportPage() {
  return (
    <UnavailableView
      title={
        <>
          COACH 360 <span className="accent">TRUTH REPORT</span>
        </>
      }
      subtitle="Complete player evaluation. Verified truth. Confident decisions."
      note="The 360 report has no evaluation to summarize and no decision to record."
    >
      <div className="rating-card">
        <div className="rating-label">TRUSTAR RATING</div>
        <Stars count={0} label="Not yet rated" />
        <p className="card-note">
          Verified evidence: all film + data confirmed by the AI Truth Engine, once evaluation is
          complete.
        </p>
      </div>
      <div className="cards-4">
        {[
          { label: "Scheme Fit", icon: "target" as const },
          { label: "Strengths", icon: "check" as const },
          { label: "Weaknesses", icon: "x" as const },
          { label: "AI Tracking Overlay", icon: "chart" as const },
        ].map((tile) => (
          <div className="card" key={tile.label}>
            <h3>
              <Icon name={tile.icon} />
              {tile.label}
            </h3>
            <p className="card-note">—</p>
          </div>
        ))}
      </div>
      <div className="card">
        <h3>
          <Icon name="target" />
          Coach Decision
        </h3>
        <div className="presets">
          {[
            "Offer — Full Scholarship",
            "Offer — Preferred Walk-On",
            "Invite — Official Visit",
            "Continue Evaluation",
            "Not a Fit",
          ].map((chip) => (
            <button className="chip" type="button" disabled style={{ opacity: 0.6 }} key={chip}>
              {chip}
            </button>
          ))}
        </div>
      </div>
    </UnavailableView>
  );
}

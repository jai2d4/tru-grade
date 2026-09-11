import { Icon } from "@/components/IconSprite";
import { Stars } from "@/components/chrome";
import { UnavailableView } from "@/components/UnavailableView";

/**
 * Coach-facing screens still without a real backend behind them.
 *
 * Coach Dashboard, Recruitment Board, and Player Profile moved to
 * @/features/coach — they read and write the real Module 7 endpoints. Coach
 * 360 Report and Genesis Search stay here as honest placeholders: the former
 * needs the AI reasoning pipeline, the latter a real athlete search index,
 * and neither exists yet.
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

export function GenesisSearchPage() {
  return (
    <UnavailableView
      title={<span className="accent">GENESIS</span>}
      subtitle="Coach search query — the AI Truth Engine for football evaluation."
      note="There is no athlete index to search."
    >
      <div className="card">
        <h3>
          <Icon name="search" />
          Natural Language Search
        </h3>
        <div className="search-fake">
          <Icon name="search" />
          e.g. &quot;Show me South Florida nickel defenders with elite TruStar fit&quot;
        </div>
        <div className="presets" style={{ marginTop: 14 }}>
          {["Class Year", "Position", "Region", "Height", "Weight", "GPA", "Verified Only"].map((chip) => (
            <button className="chip" type="button" disabled style={{ opacity: 0.6 }} key={chip}>
              {chip}
            </button>
          ))}
        </div>
        <p className="card-note" style={{ marginTop: 14 }}>
          Results will list matching verified athletes with TruStar rating and film highlights once
          Genesis search is live.
        </p>
      </div>
    </UnavailableView>
  );
}

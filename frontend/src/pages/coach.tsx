import { Icon } from "@/components/IconSprite";
import { Stars } from "@/components/chrome";
import { UnavailableView } from "@/components/UnavailableView";

/**
 * Coach-facing screens. Board counts read zero because the board is empty, not
 * because a real total was computed; no athlete is listed on any of them.
 */

export function CoachDashboardPage() {
  return (
    <UnavailableView
      title={
        <>
          COLLEGE COACH <span className="accent">DASHBOARD</span>
        </>
      }
      subtitle="Recruit. Evaluate. Win."
      note="There is no coach account, board, or watchlist behind this screen."
    >
      <div className="cards-4">
        {[
          { label: "Recruiting Board", icon: "users" as const },
          { label: "Watchlist", icon: "star" as const },
          { label: "Live Evaluations", icon: "film" as const },
          { label: "AI Truth Reports", icon: "shield" as const },
        ].map((tile) => (
          <div className="stat-tile" key={tile.label}>
            <Icon name={tile.icon} className="sm" />
            <div className="stat-label">{tile.label}</div>
            <div className="stat-val" style={{ opacity: 0.5 }}>
              —
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
          <p className="card-note">
            Athletes added to your board will appear here, filterable by position, class, state, and
            TruStar rating.
          </p>
        </div>
        <div className="card">
          <h3>
            <Icon name="target" />
            Team Needs
          </h3>
          <div className="row-list ph-row">
            {["Quarterback", "Wide Receiver", "Offensive Line"].map((row) => (
              <div className="row-item" key={row}>
                <div className="rl">{row}</div>
                <div className="rv">—</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </UnavailableView>
  );
}

export function RecruitmentBoardPage() {
  return (
    <UnavailableView
      title={
        <>
          COACH RECRUITMENT <span className="accent">BOARD</span>
        </>
      }
      subtitle="Build. Evaluate. Develop. Recruit."
      note="Nothing can be added to a board yet, so every column is empty."
    >
      <div className="cards-4">
        {[
          { label: "Watchlist", icon: "star" as const },
          { label: "Evaluating", icon: "target" as const },
          { label: "Offer Board", icon: "shield" as const },
          { label: "Development Goals", icon: "chart" as const },
        ].map((column) => (
          <div className="card" key={column.label}>
            <h3>
              <Icon name={column.icon} />
              {column.label}
            </h3>
            <p className="card-note">0 athletes</p>
          </div>
        ))}
      </div>
    </UnavailableView>
  );
}

export function PlayerProfilePage() {
  return (
    <UnavailableView
      title={
        <>
          PLAYER <span className="accent">PROFILE</span>
        </>
      }
      subtitle="Coach view — verified evidence, film, and recruiting fit."
      note="No athlete is loaded; the fit ratings below are unlit placeholders."
    >
      <div className="card">
        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          <div className="avatar-ring" style={{ width: 56, height: 56 }}>
            <svg className="ic" style={{ width: 24, height: 24 }} aria-hidden="true">
              <use href="#ic-user" />
            </svg>
          </div>
          <div>
            <h3 style={{ margin: 0 }}>Athlete Name</h3>
            <Stars count={0} label="Not yet rated" />
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
            <button className="btn-solid" type="button" disabled style={{ opacity: 0.5 }}>
              Add to Dashboard
            </button>
            <button className="chip" type="button" disabled style={{ opacity: 0.6 }}>
              Ignore Player
            </button>
          </div>
        </div>
      </div>
      <div className="cards-4">
        {[
          { label: "Scheme Fit", icon: "target" as const },
          { label: "Culture Fit", icon: "users" as const },
          { label: "Need Match", icon: "shield" as const },
          { label: "Development", icon: "chart" as const },
        ].map((tile) => (
          <div className="card" key={tile.label}>
            <h3>
              <Icon name={tile.icon} />
              {tile.label}
            </h3>
            <Stars count={0} className="mini-stars" label={`${tile.label}: not yet rated`} />
          </div>
        ))}
      </div>
      <div className="cards-2">
        <div className="card">
          <h3>
            <Icon name="film" />
            Film Archive
          </h3>
          <p className="card-note">Uploaded game film appears here once linked.</p>
        </div>
        <div className="card">
          <h3>
            <Icon name="message" />
            Coach Notes
          </h3>
          <p className="card-note">Private notes from coaching staff appear here.</p>
        </div>
      </div>
    </UnavailableView>
  );
}

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

import { Icon } from "@/components/IconSprite";
import { Stars } from "@/components/chrome";
import { UnavailableView } from "@/components/UnavailableView";

/**
 * Athlete-facing screens. All six are layout only: the ratings are unlit, the
 * counts are em dashes, and no recruiting activity is invented.
 */

export function AthleteDashboardPage() {
  return (
    <UnavailableView
      title={
        <>
          ATHLETE <span className="accent">DASHBOARD</span>
        </>
      }
      subtitle="Overview • Analyze • Elevate"
      note="Athlete profiles are not persisted yet, so there is nothing to summarize."
    >
      <div className="cards-3">
        <div className="card">
          <h3>
            <Icon name="user" />
            Athlete Overview
          </h3>
          <div className="avatar-ring">
            <Icon name="helmet" />
          </div>
          <p className="card-note">
            Name, player number, class, school colors, and verified measurables populate here once
            linked to a profile.
          </p>
        </div>
        <div className="card">
          <h3>
            <Icon name="star" />
            TruStar Rating
          </h3>
          <Stars count={0} label="Not yet rated" />
          <p className="card-note">
            AI-powered overall assessment — evaluated across performance, film, and potential.
          </p>
        </div>
        <div className="card">
          <h3>
            <Icon name="film" />
            Live Video Session
          </h3>
          <button className="btn-solid" type="button" disabled style={{ opacity: 0.5 }}>
            Start Live Session
          </button>
          <p className="card-note" style={{ marginTop: 10 }}>
            Connect, stream, and analyze in real time.
          </p>
        </div>
        <div className="card">
          <h3>
            <Icon name="target" />
            Development Goals
          </h3>
          <div className="row-list ph-row">
            {["Improve Breakaway Speed", "Enhance Vision & Patience", "Increase Yards After Contact"].map(
              (row) => (
                <div className="row-item" key={row}>
                  <div className="rl">{row}</div>
                  <div className="rv">—</div>
                </div>
              ),
            )}
          </div>
        </div>
        <div className="card">
          <h3>
            <Icon name="upload" />
            Recent Film Uploads
          </h3>
          <p className="card-note">Your uploaded game film will appear here.</p>
        </div>
        <div className="card">
          <h3>
            <Icon name="shield" />
            Recent AI Truth Reports
          </h3>
          <p className="card-note">Generated reports will appear here.</p>
        </div>
      </div>
    </UnavailableView>
  );
}

export function AiFilmReportPage() {
  return (
    <UnavailableView
      title={
        <>
          AI FILM <span className="accent">REPORT</span>
        </>
      }
      subtitle="Key clips, all film, and a coach-ready report summary."
      note="Clip selection is not built; the Film Analysis page is where real film is graded today."
    >
      <div className="card">
        <h3>
          <Icon name="film" />
          Key Clips
        </h3>
        <div className="cards-4">
          {["Route Win", "Missed Tackle", "Explosive Break", "Coach Note"].map((label) => (
            <div className="stat-tile" key={label}>
              <Icon name="play" className="sm" />
              <div className="stat-label">{label}</div>
              <div className="stat-val" style={{ opacity: 0.5 }}>
                —
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="cards-2">
        <div className="card">
          <h3>
            <Icon name="check" />
            Strengths
          </h3>
          <p className="card-note">Populated from AI film analysis once game film is processed.</p>
        </div>
        <div className="card">
          <h3>
            <Icon name="x" />
            Weaknesses
          </h3>
          <p className="card-note">Populated from AI film analysis once game film is processed.</p>
        </div>
      </div>
    </UnavailableView>
  );
}

const TRAIT_ROWS = [
  { label: "Speed", icon: "bolt" as const },
  { label: "Vision", icon: "eye" as const },
  { label: "Acceleration", icon: "bolt" as const },
  { label: "Technique", icon: "target" as const },
  { label: "Football IQ", icon: "brain" as const },
];

export function TraitBreakdownPage() {
  return (
    <UnavailableView
      title={
        <>
          TRAIT <span className="accent">BREAKDOWN</span>
        </>
      }
      subtitle="AI-powered evaluation of athletic and football traits."
      note="Trait grades come from a graded Truth Report; this athlete-facing summary is not wired up."
    >
      <div className="cards-2">
        <div className="card">
          <h3>
            <Icon name="star" />
            TruStar Trait Profile
          </h3>
          <div className="row-list">
            {TRAIT_ROWS.map((trait) => (
              <div className="row-item" key={trait.label}>
                <div className="rl">
                  <Icon name={trait.icon} />
                  {trait.label}
                </div>
                <Stars count={0} className="mini-stars" label={`${trait.label}: not yet rated`} />
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <h3>
            <Icon name="chart" />
            Evidence Clips
          </h3>
          <p className="card-note">
            Every trait links to the specific film clips behind its grade — populated once film
            analysis has run for this athlete.
          </p>
        </div>
      </div>
    </UnavailableView>
  );
}

export function RecruitingActivityPage() {
  return (
    <UnavailableView
      title={
        <>
          RECRUITMENT <span className="accent">ACTIVITY</span>
        </>
      }
      subtitle="Live updates from coaches."
      note="TruGrade receives no coach activity feed, so this page has nothing to report."
    >
      <div className="cards-3">
        <div className="card">
          <h3>
            <Icon name="users" />
            School Activity
          </h3>
          <p className="card-note">
            Recent coach activity — added to board, watchlist, camp invites — will appear here.
          </p>
        </div>
        <div className="card">
          <h3>
            <Icon name="bell" />
            Watchlist Alerts
          </h3>
          <p className="card-note">New and updated watchlist adds from college programs.</p>
        </div>
        <div className="card">
          <h3>
            <Icon name="chart" />
            Real Interest Signal
          </h3>
          <p className="card-note">Strength-of-interest scoring, separated from recruiting noise.</p>
        </div>
      </div>
    </UnavailableView>
  );
}

export function OfferProbabilityPage() {
  return (
    <UnavailableView
      title={
        <>
          OFFER <span className="accent">PROBABILITY</span>
        </>
      }
      subtitle="Trust the truth. Follow the signal."
      note="No offer model exists; the school rows below are blank templates, not real programs."
    >
      <div className="presets">
        {["All Schools", "Power 4", "Group of 5", "FCS", "JUCO"].map((chip) => (
          <button className="chip" type="button" disabled style={{ opacity: 0.6 }} key={chip}>
            {chip}
          </button>
        ))}
      </div>
      <div className="card">
        {[0, 1, 2].map((row) => (
          <div className="school-row" key={row}>
            <div className="school-badge">—</div>
            <div style={{ flex: 1 }}>
              <div className="school-name">School name</div>
              <div className="school-sub">Conference</div>
            </div>
            <Stars count={0} className="mini-stars" label="Not yet rated" />
          </div>
        ))}
        <p className="card-note" style={{ marginTop: 12 }}>
          TruStar Offer Signal uses AI to separate real recruiting interest from noise — populated
          once an athlete profile has recruiting activity.
        </p>
      </div>
    </UnavailableView>
  );
}

export function PublicRatingPage() {
  return (
    <UnavailableView
      title={
        <>
          PUBLIC ATHLETE <span className="accent">RATING</span>
        </>
      }
      subtitle="Shareable. Verified. Recruit-ready."
      note="Public profiles are not published, so there is no shareable rating."
    >
      <div className="cards-2">
        <div className="card">
          <div className="avatar-ring" style={{ width: 64, height: 64 }}>
            <svg className="ic" style={{ width: 28, height: 28 }} aria-hidden="true">
              <use href="#ic-user" />
            </svg>
          </div>
          <h3 style={{ marginTop: 12 }}>Athlete Profile</h3>
          <Stars count={0} label="Not yet rated" />
          <button className="btn-solid" type="button" disabled style={{ opacity: 0.5, marginTop: 10 }}>
            Share Athlete Profile
          </button>
        </div>
        <div className="card">
          <h3>
            <Icon name="shield" />
            AI Truth Report Preview
          </h3>
          <div className="row-list">
            <div className="row-item">
              <div className="rl">
                <Icon name="shield" />
                Evaluation Integrity
              </div>
            </div>
            <div className="row-item">
              <div className="rl">
                <Icon name="chart" />
                Performance Insights
              </div>
            </div>
            <div className="row-item">
              <div className="rl">
                <Icon name="users" />
                Recruiting Transparency
              </div>
            </div>
          </div>
          <p className="card-note">Full report available to coaches on request.</p>
        </div>
      </div>
    </UnavailableView>
  );
}

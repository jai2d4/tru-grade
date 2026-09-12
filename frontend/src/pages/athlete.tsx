import { Icon } from "@/components/IconSprite";
import { Stars } from "@/components/chrome";
import { UnavailableView } from "@/components/UnavailableView";

/**
 * Athlete-facing screens still without a real backend behind them.
 *
 * Athlete Dashboard, AI Film Report, and Trait Breakdown moved to
 * @/features/athlete — they read the real Module 5 Truth Report history.
 * The three screens left here have no data source at all: there is no
 * coach-activity feed, no offer model (the roadmap holds that one back
 * deliberately, see docs/FULL_APP_ROADMAP.md), and no public profile or
 * share-link system.
 */

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

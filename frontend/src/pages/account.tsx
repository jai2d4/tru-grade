import { Link } from "react-router-dom";
import { Icon } from "@/components/IconSprite";
import { UnavailableView } from "@/components/UnavailableView";

/**
 * Account screens — none of them are wired to an auth backend yet, so all three
 * render as unavailable states with disabled controls, exactly as they did
 * before routing existed.
 */

const DISABLED_BUTTON = { opacity: 0.5, cursor: "not-allowed" } as const;

export function LoginPage() {
  return (
    <UnavailableView
      title={
        <>
          WELCOME <span className="accent">BACK</span>
        </>
      }
      subtitle="Log in to your TruGrade account."
      note="TruGrade has no accounts yet, so there is nothing to log in to."
    >
      <div className="card" style={{ maxWidth: 420 }}>
        <div className="field">
          <Icon name="mail" />
          <div className="fbody">
            <label htmlFor="login-email">Email</label>
            <input id="login-email" type="text" placeholder="Enter your email" disabled />
          </div>
        </div>
        <div className="field">
          <Icon name="lock" />
          <div className="fbody">
            <label htmlFor="login-password">Password</label>
            <input id="login-password" type="text" placeholder="Enter your password" disabled />
          </div>
          <Icon name="eye" />
        </div>
        <button className="run" type="button" disabled style={DISABLED_BUTTON}>
          Login
        </button>
        <div className="subdivider" style={{ textAlign: "center", borderTop: "none", paddingTop: 0 }}>
          — or —
        </div>
        <Link className="chip" to="/create-account" style={{ display: "block", width: "100%", padding: 10, textAlign: "center" }}>
          Create Account
        </Link>
        <p className="card-note" style={{ textAlign: "center", marginTop: 12 }}>
          Forgot password?
        </p>
      </div>
    </UnavailableView>
  );
}

export function CreateAccountPage() {
  return (
    <UnavailableView
      title={
        <>
          CREATE YOUR <span className="accent">ACCOUNT</span>
        </>
      }
      subtitle="Join the AI Truth Engine for football evaluation."
      note="Account creation is not open."
    >
      <div className="cards-2">
        <div className="card">
          <h3>
            <Icon name="users" />I Am A…
          </h3>
          <div className="row-list">
            <div className="row-item">
              <div className="rl">
                <Icon name="helmet" />
                Athlete — track, analyze, improve.
              </div>
            </div>
            <div className="row-item">
              <div className="rl">
                <Icon name="users" />
                Parent — support and stay informed.
              </div>
            </div>
            <div className="row-item">
              <div className="rl">
                <Icon name="target" />
                Coach — evaluate and develop players.
              </div>
            </div>
            <div className="row-item">
              <div className="rl">
                <Icon name="chart" />
                Trainer — monitor health, load, performance.
              </div>
            </div>
            <div className="row-item">
              <div className="rl">
                <Icon name="shield" />
                Admin — manage teams, data, org.
              </div>
            </div>
          </div>
        </div>
        <div className="card">
          <h3>
            <Icon name="user" />
            Account Details
          </h3>
          {[
            { id: "signup-name", label: "Full Name", icon: "user" as const },
            { id: "signup-email", label: "Email Address", icon: "mail" as const },
            { id: "signup-password", label: "Password", icon: "lock" as const },
            { id: "signup-confirm", label: "Confirm Password", icon: "lock" as const },
          ].map((field) => (
            <div className="field ph-row" key={field.id}>
              <Icon name={field.icon} />
              <div className="fbody">
                <label htmlFor={field.id}>{field.label}</label>
                <input id={field.id} placeholder="—" disabled />
              </div>
            </div>
          ))}
          <button className="run" type="button" disabled style={DISABLED_BUTTON}>
            Continue <Icon name="chevron" />
          </button>
        </div>
      </div>
    </UnavailableView>
  );
}

export function AccountSettingsPage() {
  return (
    <UnavailableView
      title={
        <>
          USER <span className="accent">ACCOUNT</span>
        </>
      }
      subtitle="Manage your profile, preferences, and account settings."
      note="There is no account to manage until sign-in ships."
    >
      <div className="cards-3">
        <div className="card">
          <h3>
            <Icon name="user" />
            Profile
          </h3>
          <p className="card-note">Name, role, email, and phone on file.</p>
          <button className="chip" type="button" disabled style={{ opacity: 0.5, marginTop: 10 }}>
            Edit Profile
          </button>
        </div>
        <div className="card">
          <h3>
            <Icon name="shield" />
            Role &amp; Permissions
          </h3>
          <div className="row-list ph-row">
            {["View All Athletes", "Manage Team", "Create Reports"].map((row) => (
              <div className="row-item" key={row}>
                <div className="rl">{row}</div>
                <div className="rv">—</div>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <h3>
            <Icon name="star" />
            Subscription Plan
          </h3>
          <p className="card-note">Plan tier, renewal date, and features.</p>
        </div>
        <div className="card">
          <h3>
            <Icon name="bell" />
            Notification Preferences
          </h3>
          <div className="row-list">
            {["Evaluation Complete", "AI Report Ready", "Team Alerts"].map((row) => (
              <div className="row-item" key={row}>
                <div className="rl">{row}</div>
                <div className="toggle-fake off" />
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <h3>
            <Icon name="link" />
            Connected Accounts
          </h3>
          <div className="row-list ph-row">
            {["Hudl", "Google Drive", "Dropbox"].map((row) => (
              <div className="row-item" key={row}>
                <div className="rl">{row}</div>
                <div className="rv">Not connected</div>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <h3>
            <Icon name="lock" />
            Security Settings
          </h3>
          <p className="card-note">Password, two-factor auth, login activity.</p>
        </div>
        <div className="card">
          <h3>
            <Icon name="lock" />
            Data &amp; Privacy
          </h3>
          <p className="card-note">Data sharing, anonymization, deletion requests.</p>
        </div>
        <div className="card">
          <h3>
            <Icon name="card" />
            Billing &amp; Payment
          </h3>
          <p className="card-note">Payment method, invoices, billing details.</p>
        </div>
        <div className="card">
          <h3>
            <Icon name="upload" />
            Export &amp; Reports
          </h3>
          <p className="card-note">Download your data and scheduled reports.</p>
        </div>
      </div>
    </UnavailableView>
  );
}

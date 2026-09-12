import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ApiError } from "@/api/client";
import { auth as authApi } from "@/api/authClient";
import { LEGACY_POSITIONS, type LegacyPosition, type UserRole } from "@/api/types";
import { Icon } from "@/components/IconSprite";
import { ViewHeader } from "@/components/chrome";
import { useAuth } from "@/state/AuthContext";

/**
 * Phase 21 — real signup against app/routers/auth.py. Only Coach and
 * Athlete are real roles the backend supports; Parent/Trainer/Admin from
 * the original wireframe stay listed for context but are honestly marked
 * not yet supported rather than silently dropped or faked as working.
 */
export function CreateAccountPage() {
  const { user, loading, setUser } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [role, setRole] = useState<UserRole>("coach");
  const [position, setPosition] = useState<LegacyPosition | "">("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!loading && user) {
    return <Navigate to={user.role === "coach" ? "/coach/dashboard" : "/athlete/dashboard"} replace />;
  }

  const submit = async () => {
    setError(null);
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (role === "athlete" && !position) {
      setError("Choose a position to create an athlete account.");
      return;
    }
    setSubmitting(true);
    try {
      const current = await authApi.signup({
        email,
        password,
        full_name: fullName,
        role,
        ...(role === "athlete" ? { position: position as LegacyPosition } : {}),
      });
      setUser(current);
      navigate(current.role === "coach" ? "/coach/dashboard" : "/athlete/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the TruGrade backend.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="view">
      <ViewHeader
        title={
          <>
            CREATE YOUR <span className="accent">ACCOUNT</span>
          </>
        }
        subtitle="Join the AI Truth Engine for football evaluation."
      />
      <div className="vbody">
        <div className="cards-2">
          <div className="card">
            <h3>
              <Icon name="users" />I Am A…
            </h3>
            <div className="row-list">
              <button
                type="button"
                className="row-item"
                style={{
                  width: "100%", textAlign: "left", cursor: "pointer",
                  border: role === "coach" ? "1px solid var(--line-strong)" : undefined,
                }}
                onClick={() => setRole("coach")}
              >
                <div className="rl">
                  <Icon name="target" />
                  Coach — evaluate and develop players.
                </div>
                <div className="rv">{role === "coach" ? "Selected" : ""}</div>
              </button>
              <button
                type="button"
                className="row-item"
                style={{
                  width: "100%", textAlign: "left", cursor: "pointer",
                  border: role === "athlete" ? "1px solid var(--line-strong)" : undefined,
                }}
                onClick={() => setRole("athlete")}
              >
                <div className="rl">
                  <Icon name="helmet" />
                  Athlete — track, analyze, improve.
                </div>
                <div className="rv">{role === "athlete" ? "Selected" : ""}</div>
              </button>
              {["Parent — support and stay informed.", "Trainer — monitor health, load, performance.", "Admin — manage teams, data, org."].map((label) => (
                <div className="row-item" key={label} style={{ opacity: 0.5 }}>
                  <div className="rl">{label}</div>
                  <div className="rv">Not yet supported</div>
                </div>
              ))}
            </div>
          </div>
          <div className="card">
            <h3>
              <Icon name="user" />
              Account Details
            </h3>
            <div className="field ph-row">
              <Icon name="user" />
              <div className="fbody">
                <label htmlFor="signup-name">Full Name</label>
                <input id="signup-name" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="First Last" />
              </div>
            </div>
            <div className="field ph-row">
              <Icon name="mail" />
              <div className="fbody">
                <label htmlFor="signup-email">Email Address</label>
                <input id="signup-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" />
              </div>
            </div>
            {role === "athlete" ? (
              <div className="field ph-row">
                <Icon name="helmet" />
                <div className="fbody">
                  <label htmlFor="signup-position">Position</label>
                  <select id="signup-position" value={position} onChange={(event) => setPosition(event.target.value as LegacyPosition)}>
                    <option value="">Select a position…</option>
                    {LEGACY_POSITIONS.map((pos) => (
                      <option key={pos} value={pos}>
                        {pos}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            ) : null}
            <div className="field ph-row">
              <Icon name="lock" />
              <div className="fbody">
                <label htmlFor="signup-password">Password</label>
                <input id="signup-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="At least 8 characters" />
              </div>
            </div>
            <div className="field ph-row">
              <Icon name="lock" />
              <div className="fbody">
                <label htmlFor="signup-confirm">Confirm Password</label>
                <input id="signup-confirm" type="password" value={confirm} onChange={(event) => setConfirm(event.target.value)} placeholder="Re-enter password" />
              </div>
            </div>
            {error ? (
              <p className="card-note" role="alert" style={{ color: "var(--fail)" }}>
                {error}
              </p>
            ) : null}
            <button className="run" type="button" onClick={() => void submit()} disabled={submitting || !fullName || !email || !password}>
              {submitting ? "Creating…" : "Continue"} <Icon name="chevron" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

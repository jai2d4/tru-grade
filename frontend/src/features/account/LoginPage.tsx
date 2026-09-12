import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ApiError } from "@/api/client";
import { auth as authApi } from "@/api/authClient";
import { Icon } from "@/components/IconSprite";
import { ViewHeader } from "@/components/chrome";
import { useAuth } from "@/state/AuthContext";

/** Phase 21 — real login against app/routers/auth.py. Sets an httpOnly
 * session cookie on success; AuthContext picks it up via setUser so the
 * rest of the app sees the signed-in user immediately, no extra fetch. */
export function LoginPage() {
  const { user, loading, setUser } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!loading && user) {
    return <Navigate to={user.role === "coach" ? "/coach/dashboard" : "/athlete/dashboard"} replace />;
  }

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const current = await authApi.login({ email, password });
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
            WELCOME <span className="accent">BACK</span>
          </>
        }
        subtitle="Log in to your TruGrade account."
      />
      <div className="vbody">
        <div className="card" style={{ maxWidth: 420 }}>
          <div className="field">
            <Icon name="mail" />
            <div className="fbody">
              <label htmlFor="login-email">Email</label>
              <input
                id="login-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void submit();
                }}
                placeholder="Enter your email"
              />
            </div>
          </div>
          <div className="field">
            <Icon name="lock" />
            <div className="fbody">
              <label htmlFor="login-password">Password</label>
              <input
                id="login-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void submit();
                }}
                placeholder="Enter your password"
              />
            </div>
          </div>
          {error ? (
            <p className="card-note" role="alert" style={{ color: "var(--fail)" }}>
              {error}
            </p>
          ) : null}
          <button className="run" type="button" onClick={() => void submit()} disabled={submitting || !email || !password}>
            {submitting ? "Logging in…" : "Login"}
          </button>
          <div className="subdivider" style={{ textAlign: "center", borderTop: "none", paddingTop: 0 }}>
            — or —
          </div>
          <Link className="chip" to="/create-account" style={{ display: "block", width: "100%", padding: 10, textAlign: "center" }}>
            Create Account
          </Link>
          <p className="card-note" style={{ textAlign: "center", marginTop: 12 }}>
            Password reset isn't built yet.
          </p>
        </div>
      </div>
    </div>
  );
}

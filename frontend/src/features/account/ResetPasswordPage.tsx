import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { auth as authApi } from "@/api/authClient";
import { Icon } from "@/components/IconSprite";
import { ViewHeader } from "@/components/chrome";
import { useAuth } from "@/state/AuthContext";

/**
 * The other half of the reset flow — reads ?token= from the link
 * ForgotPasswordPage produced, sets a new password against
 * app/routers/auth.py's /reset-password, and (since that endpoint logs the
 * user straight into a fresh session on success) signs them in immediately.
 */
export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const navigate = useNavigate();
  const { setUser } = useAuth();

  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!token) return;
    setError(null);
    if (newPassword !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      const current = await authApi.resetPassword({ token, new_password: newPassword });
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
            SET A NEW <span className="accent">PASSWORD</span>
          </>
        }
        subtitle="Choose a new password for your TruGrade account."
      />
      <div className="vbody">
        <div className="card" style={{ maxWidth: 420 }}>
          {!token ? (
            <p className="unavailable-note" role="alert">
              <Icon name="x" />
              <span>
                <b>Missing reset token.</b> Use the link from your password-reset email, or{" "}
                <Link to="/forgot-password" style={{ color: "var(--blue-2)" }}>
                  request a new one
                </Link>
                .
              </span>
            </p>
          ) : (
            <>
              <div className="field">
                <Icon name="lock" />
                <div className="fbody">
                  <label htmlFor="reset-new-password">New Password</label>
                  <input
                    id="reset-new-password"
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    placeholder="At least 8 characters"
                  />
                </div>
              </div>
              <div className="field">
                <Icon name="lock" />
                <div className="fbody">
                  <label htmlFor="reset-confirm-password">Confirm Password</label>
                  <input
                    id="reset-confirm-password"
                    type="password"
                    value={confirm}
                    onChange={(event) => setConfirm(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") void submit();
                    }}
                    placeholder="Re-enter password"
                  />
                </div>
              </div>
              {error ? (
                <p className="card-note" role="alert" style={{ color: "var(--fail)" }}>
                  {error}
                  {error.toLowerCase().includes("invalid or has expired") ? (
                    <>
                      {" "}
                      <Link to="/forgot-password" style={{ color: "var(--blue-2)" }}>
                        Request a new link
                      </Link>
                      .
                    </>
                  ) : null}
                </p>
              ) : null}
              <button
                className="run"
                type="button"
                onClick={() => void submit()}
                disabled={submitting || !newPassword || !confirm}
              >
                {submitting ? "Resetting…" : "Reset Password"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

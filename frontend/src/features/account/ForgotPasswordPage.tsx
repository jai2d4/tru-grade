import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "@/api/client";
import { auth as authApi } from "@/api/authClient";
import { Icon } from "@/components/IconSprite";
import { ViewHeader } from "@/components/chrome";

/**
 * Real password reset request against app/routers/auth.py's
 * /forgot-password. Always shows the same generic confirmation regardless
 * of whether the email matched an account — the backend deliberately never
 * reveals that, so the frontend can't either.
 *
 * In a local/demo/test deployment (no email service configured), the
 * response carries the real reset link directly (`dev_reset_url`) so the
 * whole flow is testable without any email infrastructure — shown here
 * plainly, never in production.
 */
export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ detail: string; devResetUrl?: string | null } | null>(null);

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const response = await authApi.forgotPassword({ email });
      setResult({ detail: response.detail, devResetUrl: response.dev_reset_url });
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 503
            ? "Password reset isn't available yet — email delivery isn't configured for this deployment."
            : err.message
          : "Could not reach the TruGrade backend.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="view">
      <ViewHeader
        title={
          <>
            RESET YOUR <span className="accent">PASSWORD</span>
          </>
        }
        subtitle="Enter your account email and we'll send you a reset link."
      />
      <div className="vbody">
        <div className="card" style={{ maxWidth: 420 }}>
          {result ? (
            <>
              <p className="card-note">
                <Icon name="check" className="sm" /> {result.detail}
              </p>
              {result.devResetUrl ? (
                <div className="field" style={{ marginTop: 10 }}>
                  <Icon name="link" />
                  <div className="fbody">
                    <label htmlFor="dev-reset-link">Local/dev link (no email service configured)</label>
                    <input
                      id="dev-reset-link"
                      type="text"
                      readOnly
                      value={result.devResetUrl}
                      onFocus={(event) => event.currentTarget.select()}
                    />
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <>
              <div className="field">
                <Icon name="mail" />
                <div className="fbody">
                  <label htmlFor="forgot-email">Email</label>
                  <input
                    id="forgot-email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") void submit();
                    }}
                    placeholder="Enter your account email"
                  />
                </div>
              </div>
              {error ? (
                <p className="card-note" role="alert" style={{ color: "var(--fail)" }}>
                  {error}
                </p>
              ) : null}
              <button className="run" type="button" onClick={() => void submit()} disabled={submitting || !email}>
                {submitting ? "Sending…" : "Send Reset Link"}
              </button>
            </>
          )}
          <div className="subdivider" style={{ textAlign: "center", borderTop: "none", paddingTop: 0 }}>
            — or —
          </div>
          <Link className="chip" to="/login" style={{ display: "block", width: "100%", padding: 10, textAlign: "center" }}>
            Back to Login
          </Link>
        </div>
      </div>
    </div>
  );
}

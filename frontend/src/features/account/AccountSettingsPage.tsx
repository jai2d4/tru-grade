import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { athletes as athletesApi } from "@/api/coachClient";
import type { Athlete } from "@/api/types";
import { Icon } from "@/components/IconSprite";
import { ViewHeader } from "@/components/chrome";
import { useAuth } from "@/state/AuthContext";

/**
 * Phase 21 — the real account settings screen: who you are, and logout.
 * Billing, notifications, connected accounts, 2FA, and data export from the
 * original wireframe are still genuinely unbuilt — said plainly in one note
 * rather than shown as fake cards with static "Not connected" rows.
 */
export function AccountSettingsPage() {
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();
  const [athlete, setAthlete] = useState<Athlete | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    if (user?.role === "athlete" && user.athlete_id) {
      athletesApi.get(user.athlete_id).then(setAthlete).catch(() => setAthlete(null));
    }
  }, [user]);

  if (loading) {
    return (
      <div className="view">
        <ViewHeader title={<>USER <span className="accent">ACCOUNT</span></>} subtitle="Manage your profile and account settings." />
        <div className="vbody">
          <p className="card-note">Loading…</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="view">
        <ViewHeader title={<>USER <span className="accent">ACCOUNT</span></>} subtitle="Manage your profile and account settings." />
        <div className="vbody">
          <p className="unavailable-note" role="note">
            <Icon name="clock" />
            <span>
              <b>Not signed in.</b> <Link to="/login" style={{ color: "var(--blue-2)" }}>Log in</Link> or{" "}
              <Link to="/create-account" style={{ color: "var(--blue-2)" }}>create an account</Link> to manage settings.
            </span>
          </p>
        </div>
      </div>
    );
  }

  const doLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
      navigate("/login");
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <div className="view">
      <ViewHeader title={<>USER <span className="accent">ACCOUNT</span></>} subtitle="Manage your profile and account settings." />
      <div className="vbody">
        <div className="cards-2">
          <div className="card">
            <h3>
              <Icon name="user" />
              Profile
            </h3>
            <div className="row-list">
              <div className="row-item">
                <div className="rl">Name</div>
                <div className="rv">{user.full_name}</div>
              </div>
              <div className="row-item">
                <div className="rl">Email</div>
                <div className="rv">{user.email}</div>
              </div>
              <div className="row-item">
                <div className="rl">Role</div>
                <div className="rv" style={{ textTransform: "capitalize" }}>{user.role}</div>
              </div>
              <div className="row-item">
                <div className="rl">Member Since</div>
                <div className="rv">{new Date(user.created_at).toLocaleDateString()}</div>
              </div>
            </div>
          </div>

          {user.role === "athlete" ? (
            <div className="card">
              <h3>
                <Icon name="helmet" />
                Linked Athlete Profile
              </h3>
              {athlete ? (
                <div className="row-list">
                  <div className="row-item">
                    <div className="rl">Position</div>
                    <div className="rv">{athlete.position}</div>
                  </div>
                  <div className="row-item">
                    <div className="rl">School</div>
                    <div className="rv">{athlete.school ?? "—"}</div>
                  </div>
                </div>
              ) : (
                <p className="card-note">Loading…</p>
              )}
              <p className="card-note" style={{ marginTop: 9 }}>
                See your full profile on{" "}
                <Link to={`/athlete/dashboard?athleteId=${user.athlete_id}`} style={{ color: "var(--blue-2)" }}>
                  Athlete Dashboard
                </Link>
                .
              </p>
            </div>
          ) : (
            <div className="card">
              <h3>
                <Icon name="shield" />
                Security
              </h3>
              <p className="card-note">
                Password reset and two-factor authentication aren't built yet.
              </p>
            </div>
          )}
        </div>

        <div className="card" style={{ marginTop: 16 }}>
          <button className="chip" type="button" onClick={() => void doLogout()} disabled={loggingOut}>
            {loggingOut ? "Logging out…" : "Log Out"}
          </button>
        </div>

        <p className="unavailable-note" role="note" style={{ marginTop: 16 }}>
          <Icon name="clock" />
          <span>
            <b>Not built yet.</b> Billing &amp; payment, notification preferences, connected accounts
            (Hudl, Google Drive, Dropbox), and data export/deletion requests have no backend behind
            them, so they aren't shown here rather than shown as fake toggles.
          </span>
        </p>
      </div>
    </div>
  );
}

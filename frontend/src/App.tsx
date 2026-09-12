import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { CreateProfilePage } from "@/features/profile/CreateProfilePage";
import { FilmAnalysisPage } from "@/features/film/FilmAnalysisPage";
import { AccountSettingsPage } from "@/features/account/AccountSettingsPage";
import { CreateAccountPage } from "@/features/account/CreateAccountPage";
import { LoginPage } from "@/features/account/LoginPage";
import { OfferProbabilityPage, RecruitingActivityPage } from "@/pages/athlete";
import { AiFilmReportPage } from "@/features/athlete/AiFilmReportPage";
import { AthleteDashboardPage } from "@/features/athlete/AthleteDashboardPage";
import { PublicRatingPage } from "@/features/athlete/PublicRatingPage";
import { TraitBreakdownPage } from "@/features/athlete/TraitBreakdownPage";
import { Coach360ReportPage } from "@/features/coach/Coach360ReportPage";
import { CoachDashboardPage } from "@/features/coach/CoachDashboardPage";
import { GenesisSearchPage } from "@/features/coach/GenesisSearchPage";
import { PlayerProfilePage } from "@/features/coach/PlayerProfilePage";
import { RecruitmentBoardPage } from "@/features/coach/RecruitmentBoardPage";
import { PublicAthletePage } from "@/features/public/PublicAthletePage";
import { AuthProvider } from "@/state/AuthContext";
import { ProfileProvider } from "@/state/ProfileContext";

/**
 * Every one of the sixteen Phase 15 views now has its own path, so reload and
 * back/forward land on the screen the user was looking at.
 *
 * The profile form sits above the routes: Film Analysis falls back to the
 * player number and school colors it collects, and neither view should lose
 * what was typed when the other is opened.
 */
export function App() {
  return (
    <AuthProvider>
      <ProfileProvider>
        <Routes>
          {/* Anonymous share-link landing page — no account, no sidebar, so it
              sits outside AppShell entirely rather than under any coach/athlete
              path. See app/routers/public.py for what it can and can't show. */}
          <Route path="public/:token" element={<PublicAthletePage />} />

          <Route element={<AppShell />}>
            <Route index element={<CreateProfilePage />} />
            <Route path="film-analysis" element={<FilmAnalysisPage />} />

            <Route path="login" element={<LoginPage />} />
            <Route path="create-account" element={<CreateAccountPage />} />
            <Route path="account" element={<AccountSettingsPage />} />

            <Route path="athlete">
              <Route path="dashboard" element={<AthleteDashboardPage />} />
              <Route path="film-report" element={<AiFilmReportPage />} />
              <Route path="traits" element={<TraitBreakdownPage />} />
              <Route path="recruiting" element={<RecruitingActivityPage />} />
              <Route path="offers" element={<OfferProbabilityPage />} />
              <Route path="public-rating" element={<PublicRatingPage />} />
            </Route>

            <Route path="coach">
              <Route path="dashboard" element={<CoachDashboardPage />} />
              <Route path="board" element={<RecruitmentBoardPage />} />
              <Route path="player-profile" element={<PlayerProfilePage />} />
              <Route path="360-report" element={<Coach360ReportPage />} />
              <Route path="genesis" element={<GenesisSearchPage />} />
            </Route>

            {/* An unknown path is not an error state to invent a screen for. */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </ProfileProvider>
    </AuthProvider>
  );
}

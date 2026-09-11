import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { CreateProfilePage } from "@/features/profile/CreateProfilePage";
import { FilmAnalysisPage } from "@/features/film/FilmAnalysisPage";
import { AccountSettingsPage, CreateAccountPage, LoginPage } from "@/pages/account";
import { OfferProbabilityPage, PublicRatingPage, RecruitingActivityPage } from "@/pages/athlete";
import { Coach360ReportPage, GenesisSearchPage } from "@/pages/coach";
import { AiFilmReportPage } from "@/features/athlete/AiFilmReportPage";
import { AthleteDashboardPage } from "@/features/athlete/AthleteDashboardPage";
import { TraitBreakdownPage } from "@/features/athlete/TraitBreakdownPage";
import { CoachDashboardPage } from "@/features/coach/CoachDashboardPage";
import { PlayerProfilePage } from "@/features/coach/PlayerProfilePage";
import { RecruitmentBoardPage } from "@/features/coach/RecruitmentBoardPage";
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
    <ProfileProvider>
      <Routes>
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
  );
}

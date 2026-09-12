import { useSearchParams } from "react-router-dom";
import { useAuth } from "@/state/AuthContext";

/**
 * The athleteId a screen should read from — the URL's ?athleteId= if one is
 * present (a coach viewing a specific prospect, or any link that already
 * names one), otherwise the signed-in athlete's own linked roster row, if
 * they're logged in as one. A coach with no ?athleteId still sees the
 * SelectAthletePrompt fallback, same as before Phase 21 accounts existed.
 */
export function useEffectiveAthleteId(): string | null {
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const fromUrl = searchParams.get("athleteId");
  if (fromUrl) return fromUrl;
  return user?.role === "athlete" ? (user.athlete_id ?? null) : null;
}

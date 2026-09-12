import { createContext, useContext, useMemo, useRef, useState, type ReactNode } from "react";

/**
 * The athlete profile the Create Profile form collects.
 *
 * Phase 15 kept these in the DOM, and Film Analysis reached across the page to
 * read them — `v2StartAutomaticIdentity` fell back to `#playerNumber` and
 * `#schoolColors` when its own jersey/team fields were empty. Once each view
 * has its own route those inputs no longer share a document, so the same values
 * live here instead and the fallback keeps working across a navigation.
 */

export interface ProfileState {
  athleteName: string;
  playerNumber: string;
  classYear: string;
  stateInput: string;
  school: string;
  schoolColors: string;
  height: string;
  weight: string;
  gpa: string;
  ytUrl: string;
}

export const EMPTY_PROFILE: ProfileState = {
  athleteName: "",
  playerNumber: "",
  classYear: "",
  stateInput: "",
  school: "",
  schoolColors: "",
  height: "",
  weight: "",
  gpa: "",
  ytUrl: "",
};

interface ProfileContextValue {
  profile: ProfileState;
  setProfile: (update: (prev: ProfileState) => ProfileState) => void;
  /**
   * The latest profile without waiting for a re-render — the equivalent of the
   * old `document.getElementById(...).value` read, for use inside callbacks.
   */
  readProfile: () => ProfileState;
}

const ProfileContext = createContext<ProfileContextValue | null>(null);

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfileState] = useState<ProfileState>(EMPTY_PROFILE);
  const latest = useRef(profile);
  latest.current = profile;

  const value = useMemo<ProfileContextValue>(
    () => ({
      profile,
      setProfile: (update) => {
        setProfileState((prev) => {
          const next = update(prev);
          latest.current = next;
          return next;
        });
      },
      readProfile: () => latest.current,
    }),
    [profile],
  );

  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>;
}

export function useProfile(): ProfileContextValue {
  const value = useContext(ProfileContext);
  if (!value) throw new Error("useProfile must be used inside <ProfileProvider>");
  return value;
}

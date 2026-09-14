/**
 * The sidebar's contents, and the single source of truth for the app's URLs.
 *
 * The Phase 15 page swapped `hidden` on sixteen sibling `<div class="view">`
 * elements, so every screen shared one URL. Each of those views now has a real
 * path; the group labels, order, copy and `soon` badges are unchanged.
 */
import type { IconName } from "@/components/IconSprite";

export interface NavItem {
  label: string;
  to: string;
  icon: IconName;
  /** Renders the `soon` badge and marks the route as an unavailable state. */
  soon?: boolean;
  /** True when the link points at a section of an already-routed page. */
  anchor?: boolean;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "The Tool",
    items: [
      { label: "Create Profile", to: "/", icon: "helmet" },
      { label: "Film Analysis", to: "/film-analysis", icon: "film" },
      { label: "AI Truth Report", to: "/#report", icon: "shield", anchor: true },
    ],
  },
  {
    label: "Account",
    items: [
      { label: "Login", to: "/login", icon: "lock" },
      { label: "Create Account", to: "/create-account", icon: "user" },
      { label: "Account Settings", to: "/account", icon: "gear" },
    ],
  },
  {
    label: "Athlete",
    items: [
      { label: "Dashboard", to: "/athlete/dashboard", icon: "home" },
      { label: "AI Film Report", to: "/athlete/film-report", icon: "film" },
      { label: "Trait Breakdown", to: "/athlete/traits", icon: "star" },
      { label: "Recruiting Activity", to: "/athlete/recruiting", icon: "bell", soon: true },
      { label: "Offer Probability", to: "/athlete/offers", icon: "target", soon: true },
      { label: "Public Rating", to: "/athlete/public-rating", icon: "link" },
    ],
  },
  {
    label: "Coach",
    items: [
      { label: "Coach Dashboard", to: "/coach/dashboard", icon: "home" },
      { label: "Recruitment Board", to: "/coach/board", icon: "users" },
      { label: "Player Profile", to: "/coach/player-profile", icon: "user" },
      { label: "Coach 360 Report", to: "/coach/360-report", icon: "brain" },
      { label: "Genesis Search", to: "/coach/genesis", icon: "search" },
    ],
  },
];

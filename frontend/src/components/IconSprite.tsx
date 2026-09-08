/**
 * The icon sprite, lifted verbatim from the Phase 15 page.
 *
 * Every glyph keeps its original `ic-*` id, so the stylesheet's `.ic` rules and
 * every `<use href="#ic-…">` reference behave exactly as before. Rendered once
 * at the top of the shell; `<Icon>` below points at it.
 */

export type IconName =
  | "helmet"
  | "ruler"
  | "scale"
  | "clock"
  | "dumbbell"
  | "book"
  | "user"
  | "upload"
  | "play"
  | "star"
  | "check"
  | "x"
  | "flag"
  | "shield"
  | "bolt"
  | "chevron"
  | "arrow"
  | "mail"
  | "lock"
  | "eye"
  | "bell"
  | "brain"
  | "chart"
  | "target"
  | "search"
  | "film"
  | "home"
  | "gear"
  | "message"
  | "calendar"
  | "card"
  | "link"
  | "users"
  ;

export function IconSprite() {
  return (
    <svg style={{ display: "none" }} aria-hidden="true">
      <symbol id="ic-helmet" viewBox="0 0 24 24"><path d="M3 13c0-5 4-9 9-9s9 4 9 9v2a2 2 0 0 1-2 2h-2.5l-1 3h-7l-1-3H5a2 2 0 0 1-2-2z"/><path d="M12 4v16"/></symbol>
      <symbol id="ic-ruler" viewBox="0 0 24 24"><rect x="4" y="9" width="16" height="6" rx="1"/><path d="M7 9v2M10 9v3M13 9v2M16 9v3"/></symbol>
      <symbol id="ic-scale" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/></symbol>
      <symbol id="ic-clock" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M12 7v5l4 2"/></symbol>
      <symbol id="ic-dumbbell" viewBox="0 0 24 24"><path d="M4 9v6M7 7v10M17 7v10M20 9v6M7 12h10"/></symbol>
      <symbol id="ic-book" viewBox="0 0 24 24"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H12v18H6.5A2.5 2.5 0 0 0 4 23z"/><path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H12v18h5.5a2.5 2.5 0 0 1 2.5 2z"/></symbol>
      <symbol id="ic-user" viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/></symbol>
      <symbol id="ic-upload" viewBox="0 0 24 24"><path d="M12 16V4M8 8l4-4 4 4"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></symbol>
      <symbol id="ic-play" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M10 8.5l6 3.5-6 3.5z"/></symbol>
      <symbol id="ic-star" viewBox="0 0 24 24"><path d="M12 2l2.9 6.6 7.1.6-5.4 4.7 1.7 7-6.3-3.9-6.3 3.9 1.7-7L2 9.2l7.1-.6z"/></symbol>
      <symbol id="ic-check" viewBox="0 0 24 24"><path d="M4 12.5l5 5L20 6"/></symbol>
      <symbol id="ic-x" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></symbol>
      <symbol id="ic-flag" viewBox="0 0 24 24"><path d="M5 3v18"/><path d="M5 4h11l-2.5 3.5L16 11H5"/></symbol>
      <symbol id="ic-shield" viewBox="0 0 24 24"><path d="M12 3l7 3v6c0 5-3.5 8-7 9-3.5-1-7-4-7-9V6z"/></symbol>
      <symbol id="ic-bolt" viewBox="0 0 24 24"><path d="M13 2 4 14h6l-1 8 9-12h-6z"/></symbol>
      <symbol id="ic-chevron" viewBox="0 0 24 24"><path d="M8 5l6 7-6 7"/><path d="M13 5l6 7-6 7"/></symbol>
      <symbol id="ic-arrow" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></symbol>
      <symbol id="ic-mail" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M4 6l8 7 8-7"/></symbol>
      <symbol id="ic-lock" viewBox="0 0 24 24"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></symbol>
      <symbol id="ic-eye" viewBox="0 0 24 24"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></symbol>
      <symbol id="ic-bell" viewBox="0 0 24 24"><path d="M6 10a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6z"/><path d="M9.5 20a2.5 2.5 0 0 0 5 0"/></symbol>
      <symbol id="ic-brain" viewBox="0 0 24 24"><path d="M9 4a3 3 0 0 0-3 3v1a3 3 0 0 0-1 5.5V15a3 3 0 0 0 3 3h1"/><path d="M15 4a3 3 0 0 1 3 3v1a3 3 0 0 1 1 5.5V15a3 3 0 0 1-3 3h-1"/><path d="M9 4a3 3 0 0 1 6 0v14a3 3 0 0 1-6 0"/></symbol>
      <symbol id="ic-chart" viewBox="0 0 24 24"><path d="M4 20V10M11 20V4M18 20v-7"/></symbol>
      <symbol id="ic-target" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r=".7" fill="currentColor" stroke="none"/></symbol>
      <symbol id="ic-search" viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M20 20l-4.8-4.8"/></symbol>
      <symbol id="ic-film" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 5v14M16 5v14M3 10h5M16 10h5M3 15h5M16 15h5"/></symbol>
      <symbol id="ic-home" viewBox="0 0 24 24"><path d="M4 11l8-7 8 7"/><path d="M6 10v9h12v-9"/></symbol>
      <symbol id="ic-gear" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3.2"/><path d="M12 3v2.5M12 18.5V21M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M3 12h2.5M18.5 12H21M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/></symbol>
      <symbol id="ic-message" viewBox="0 0 24 24"><path d="M4 5h16v11H8l-4 4z"/></symbol>
      <symbol id="ic-calendar" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></symbol>
      <symbol id="ic-card" viewBox="0 0 24 24"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20M6 15h4"/></symbol>
      <symbol id="ic-link" viewBox="0 0 24 24"><path d="M9 15l6-6"/><path d="M8 12l-2.5 2.5a3.5 3.5 0 0 0 5 5L13 17"/><path d="M16 12l2.5-2.5a3.5 3.5 0 0 0-5-5L11 7"/></symbol>
      <symbol id="ic-users" viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.2"/><path d="M2.5 20c0-3.6 2.9-6.5 6.5-6.5S15.5 16.4 15.5 20"/><circle cx="17.5" cy="9" r="2.6"/><path d="M15.8 13.3c2.6.4 4.7 2.7 4.7 5.5"/></symbol>
    </svg>
  );
}

interface IconProps {
  name: IconName;
  /** Extra sprite classes, e.g. "sm" or "fill" — `ic` is always applied. */
  className?: string;
}

/**
 * Decorative by default: the sprite carries no meaning a screen reader needs,
 * because every icon in this UI sits next to its own text label.
 */
export function Icon({ name, className }: IconProps) {
  return (
    <svg className={className ? `ic ${className}` : "ic"} aria-hidden="true" focusable="false">
      <use href={`#ic-${name}`} />
    </svg>
  );
}

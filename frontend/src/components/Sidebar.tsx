import { NavLink, useLocation } from "react-router-dom";
import { Icon } from "./IconSprite";
import { NAV_GROUPS, type NavItem } from "@/navigation";

interface SidebarProps {
  /** Only meaningful below the 860px breakpoint, where the rail is a drawer. */
  open: boolean;
  onNavigate: () => void;
}

/**
 * On desktop this is the always-present 230px rail from Phase 15. Below 860px
 * the stylesheet turns it into an off-canvas drawer; `aria-hidden` and
 * `inert`-style tab removal are handled by keeping focusable children out of
 * the tab order while it is closed.
 */
export function Sidebar({ open, onNavigate }: SidebarProps) {
  const location = useLocation();

  return (
    <nav className="sidebar" id="trugrade-sidebar" aria-label="Sections">
      <div className="sidebar-brand">
        <img
          src="./trugrade-mark.jpg"
          alt=""
          width={24}
          height={24}
          style={{ width: 24, height: 24, borderRadius: 4, display: "block" }}
        />
        <span className="sidebar-brand-word">
          <span className="tru">Tru</span>
          <span className="grade">Grade</span>
        </span>
      </div>

      {NAV_GROUPS.map((group) => (
        <div key={group.label}>
          <div className="sidebar-group-label">{group.label}</div>
          {group.items.map((item) => (
            <SidebarLink
              key={item.label}
              item={item}
              tabbable={open || !isDrawer()}
              currentHash={location.hash}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      ))}
    </nav>
  );
}

/**
 * The drawer only exists below the CSS breakpoint. `matchMedia` is absent in
 * some test environments, so treat its absence as "desktop", where the rail is
 * always reachable.
 */
function isDrawer(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(max-width: 860px)").matches;
}

interface SidebarLinkProps {
  item: NavItem;
  tabbable: boolean;
  currentHash: string;
  onNavigate: () => void;
}

function SidebarLink({ item, tabbable, currentHash, onNavigate }: SidebarLinkProps) {
  // "AI Truth Report" targets a section of Create Profile rather than its own
  // page, so it is active only when that hash is actually on the URL — and the
  // plain "Create Profile" link is not active at the same time.
  const anchorActive = item.anchor && currentHash === "#report";

  return (
    <NavLink
      to={item.to}
      end={item.to === "/"}
      onClick={onNavigate}
      tabIndex={tabbable ? undefined : -1}
      className={({ isActive }) => {
        const active = item.anchor ? anchorActive : isActive && !(item.to === "/" && currentHash === "#report");
        return active ? "nav-item active" : "nav-item";
      }}
    >
      <Icon name={item.icon} />
      {item.label}
      {item.soon ? <span className="nav-badge">soon</span> : null}
    </NavLink>
  );
}

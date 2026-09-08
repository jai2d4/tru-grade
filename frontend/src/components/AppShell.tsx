import { useEffect, useRef, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { IconSprite } from "./IconSprite";
import { Sidebar } from "./Sidebar";

/**
 * The persistent chrome: icon sprite, sidebar rail, and the routed view.
 *
 * Phase 15's `showView()` scrolled to top on every switch and optionally
 * scrolled to the report anchor. Both behaviours live here now, driven by the
 * URL instead of by the click handler, so a reload or a back/forward step
 * reproduces them.
 */
export function AppShell() {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const mainRef = useRef<HTMLElement>(null);

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  // Escape closes the drawer, matching the usual dialog affordance.
  useEffect(() => {
    if (!sidebarOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSidebarOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sidebarOpen]);

  // Scroll behaviour, carried over from showView(): top on navigation, or the
  // report section when the URL asks for it.
  useEffect(() => {
    if (location.hash === "#report") {
      const target = document.getElementById("report");
      if (target) {
        const timer = window.setTimeout(
          () => target.scrollIntoView({ behavior: "smooth", block: "start" }),
          30,
        );
        return () => window.clearTimeout(timer);
      }
      return;
    }
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
    return;
  }, [location.pathname, location.hash]);

  return (
    <>
      <IconSprite />
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <div className="shell" data-sidebar={sidebarOpen ? "open" : "closed"}>
        <Sidebar open={sidebarOpen} onNavigate={() => setSidebarOpen(false)} />
        {sidebarOpen ? (
          <button
            type="button"
            className="sidebar-scrim"
            aria-label="Close navigation"
            onClick={() => setSidebarOpen(false)}
          />
        ) : null}
        <main className="main" id="main-content" ref={mainRef} tabIndex={-1}>
          <button
            type="button"
            className="sidebar-toggle"
            aria-expanded={sidebarOpen}
            aria-controls="trugrade-sidebar"
            onClick={() => setSidebarOpen((value) => !value)}
          >
            Menu
          </button>
          <Outlet />
        </main>
      </div>
    </>
  );
}

import type { ReactNode } from "react";
import { Icon } from "./IconSprite";
import { ViewHeader } from "./chrome";

interface UnavailableViewProps {
  title: ReactNode;
  subtitle: string;
  /**
   * What this screen will show once it is built. Stated plainly so the layout
   * below is unmistakably a placeholder rather than a reading of real data.
   */
  note: string;
  children: ReactNode;
}

/**
 * Shell for every screen that is not built yet.
 *
 * The placeholder layouts underneath are the Phase 15 markup unchanged: em
 * dashes, unlit stars, zero counts and "will appear here" copy. Nothing here
 * fabricates a grade, an offer, or recruiting activity — the point of the
 * screen is to show the shape of the page while saying it holds no data.
 */
export function UnavailableView({ title, subtitle, note, children }: UnavailableViewProps) {
  return (
    <div className="view">
      <ViewHeader title={title} subtitle={subtitle} badge="COMING SOON" />
      <div className="vbody">
        <p className="unavailable-note" role="note">
          <Icon name="clock" />
          <span>
            <b>Not available yet.</b> {note} Every field below is an empty placeholder — no athlete,
            grade, or recruiting data is shown on this screen.
          </span>
        </p>
        {children}
      </div>
    </div>
  );
}

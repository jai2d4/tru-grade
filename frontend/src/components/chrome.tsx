import type { CSSProperties, ReactNode } from "react";
import { Icon } from "./IconSprite";

/**
 * Small presentational pieces shared across views, carried over from the
 * Phase 15 markup with their class names and copy unchanged.
 */

/** The header strip above Create Profile: brand lockup, stepper, engine label. */
export function TopBar() {
  return (
    <div className="top">
      <div className="brand">
        <img className="brand-mark" src="/trugrade-mark.jpg" alt="TruGrade" />
        <div className="brand-txt">
          <span className="brand-word">
            <span className="tru">Tru</span>
            <span className="grade">Grade</span>
          </span>
          <span className="brand-sub">AI Truth Engine for Football Evaluation</span>
        </div>
      </div>
      <div className="stepper" aria-hidden="true">
        <svg className="stp active">
          <use href="#ic-star" />
        </svg>
        <span className="seg" />
        <svg className="stp">
          <use href="#ic-star" />
        </svg>
        <span className="seg" />
        <svg className="stp">
          <use href="#ic-star" />
        </svg>
        <span className="seg" />
        <svg className="stp">
          <use href="#ic-star" />
        </svg>
        <span className="seg" />
        <svg className="stp">
          <use href="#ic-star" />
        </svg>
        <span className="seg" />
        <svg className="stp">
          <use href="#ic-star" />
        </svg>
      </div>
      <div className="env">gemini-3.5-flash &nbsp;·&nbsp; metric sieve v1.0</div>
    </div>
  );
}

/** The footer strip on Create Profile. */
export function TrustBar() {
  return (
    <div className="trust-bar">
      <div className="trust-left">
        <Stars count={5} className="trust-stars" />
        <div className="trust-copy">
          Trust the <span className="accent">Truth</span>.<small>Powered by AI. Validated by film.</small>
        </div>
      </div>
      <div className="badges">
        <div className="badge">
          <Icon name="shield" />
          AI Truth Engine
        </div>
        <div className="badge">
          <Icon name="play" />
          Live Film Processing
        </div>
        <div className="badge">
          <Icon name="bolt" />
          Biomechanical Analysis
        </div>
        <div className="badge">
          <Icon name="check" />
          Trusted Evaluation
        </div>
      </div>
    </div>
  );
}

interface StarsProps {
  /** How many of `total` are lit. */
  count: number;
  total?: number;
  className?: string;
  starClassName?: string;
  label?: string;
}

/**
 * The star readout. Unlit stars are the honest default: an empty row means no
 * rating has been produced, not a rating of zero, so the accessible label says
 * so rather than announcing "0 out of 5".
 */
export function Stars({ count, total = 5, className = "stars", starClassName = "star", label }: StarsProps) {
  return (
    <div className={className} role="img" aria-label={label ?? (count > 0 ? `${count} of ${total} stars` : "Not yet rated")}>
      {Array.from({ length: total }, (_, index) => (
        <svg key={index} className={index < count ? `${starClassName} lit` : starClassName}>
          <use href="#ic-star" />
        </svg>
      ))}
    </div>
  );
}

interface ViewHeaderProps {
  title: ReactNode;
  subtitle: string;
  /** The badge on the right — "COMING SOON" for unavailable views. */
  badge?: ReactNode;
  badgeClassName?: string;
  badgeStyle?: CSSProperties;
}

/** The `.vh` block that heads every routed view apart from Create Profile. */
export function ViewHeader({ title, subtitle, badge, badgeClassName = "soon", badgeStyle }: ViewHeaderProps) {
  return (
    <div className="vh">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {badge ? (
        <span className={badgeClassName} style={badgeStyle}>
          {badge}
        </span>
      ) : null}
    </div>
  );
}

interface PageHeadProps {
  title: ReactNode;
  subtitle: string;
}

/** The `.page-head` block on Create Profile. */
export function PageHead({ title, subtitle }: PageHeadProps) {
  return (
    <div className="page-head">
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </div>
  );
}

export interface PipelineStep {
  label: string;
  state: "done" | "active" | "err" | "";
}

/** Port of `pipelineHTML` — the film upload progress strip. */
export function Pipeline({ steps }: { steps: PipelineStep[] }) {
  return (
    <div className="pipeline">
      {steps.map((step, index) => (
        <div key={`${step.label}-${index}`} className={step.state ? `step ${step.state}` : "step"}>
          {step.state === "done" ? "●" : step.state === "active" ? "◐" : step.state === "err" ? "✕" : "○"} {step.label}
        </div>
      ))}
    </div>
  );
}

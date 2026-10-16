import type { ReactNode } from "react";

/**
 * Standard page header: a display-accent title with an optional lede and
 * optional actions placed opposite the title. On narrow screens the actions
 * drop below the title. Eyebrow labels are intentionally not rendered.
 */
export function PageHeader({
  title,
  description,
  tooltip,
  children,
}: {
  title: string;
  description?: string;
  tooltip?: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="page-header-text">
        <h1 className="page-title display-accent">{title}</h1>
        {description || tooltip ? (
          <p className="page-lede">
            {description}
            {description && tooltip ? " " : null}
            {tooltip ? (
              <span
                className="help-icon"
                tabIndex={0}
                role="button"
                aria-label={tooltip}>
                ?
                <span className="help-tooltip" role="tooltip">
                  {tooltip}
                </span>
              </span>
            ) : null}
          </p>
        ) : null}
      </div>
      {children ? <div className="page-header-actions">{children}</div> : null}
    </header>
  );
}

import type { ReactNode } from "react";

/**
 * Standard page header: a display-accent title with an optional lede and
 * optional actions placed opposite the title. On narrow screens the actions
 * drop below the title. Eyebrow labels are intentionally not rendered.
 */
export function PageHeader({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="page-header-text">
        <h1 className="page-title display-accent">{title}</h1>
        {description ? <p className="page-lede">{description}</p> : null}
      </div>
      {children ? <div className="page-header-actions">{children}</div> : null}
    </header>
  );
}

import type { ReactNode } from "react";

/**
 * Standard page header: a display-accent title with an optional lede and
 * optional actions. Eyebrow labels are intentionally not rendered.
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
      <h1 className="page-title display-accent">{title}</h1>
      {description ? <p className="page-lede">{description}</p> : null}
      {children}
    </header>
  );
}

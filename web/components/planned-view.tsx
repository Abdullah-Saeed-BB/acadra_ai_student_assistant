import Link from "next/link";
import { PageHeader } from "@/components/page-header";

/**
 * A branded placeholder for a route that is planned but not built yet. It keeps
 * navigation honest: no dead 404s while the workspace pages are implemented one
 * by one.
 */
export function PlannedView({
  title,
  description,
  note,
}: {
  title: string;
  description: string;
  note?: string;
}) {
  return (
    <div className="page">
      <PageHeader title={title} description={description} />

      <section className="panel">
        <p className="panel-note">
          This page is scaffolded so navigation works end to end. When its backend route is
          ready it will read and write through the REST boundary, the same way manual source
          entry does today.
        </p>
        {note ? <p className="panel-note">{note}</p> : null}
        <div className="page-actions">
          <Link className="connect-button" href="/">
            Back to Today
          </Link>
          <Link className="page-link" href="/sources/new">
            Add a source
          </Link>
        </div>
      </section>
    </div>
  );
}

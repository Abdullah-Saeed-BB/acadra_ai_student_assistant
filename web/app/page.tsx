import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Today",
};

export default function TodayPage() {
  return (
    <div className="page">
      <header className="page-header">
        <p className="eyebrow">Today</p>
        <h1 className="page-title display-accent">Today</h1>
        <p className="page-lede">
          Your short list for the day. Every step names the action, how long it takes, and
          why it matters now, with the source it came from kept beside it.
        </p>
      </header>

      <dl className="stat-row">
        <div className="stat">
          <dt>Steps today</dt>
          <dd className="tnum">0</dd>
        </div>
        <div className="stat">
          <dt>Estimated effort</dt>
          <dd className="tnum">0 min</dd>
        </div>
      </dl>

      <section className="sheet" aria-labelledby="today-state-title">
        <div className="sheet-margin">
          <p className="sheet-label">Source</p>
          <p className="sheet-source">No source yet</p>
          <p className="sheet-meta">Observed time and field appear here.</p>
          <p className="sheet-field">What changed</p>
        </div>

        <div className="sheet-main">
          <h2 id="today-state-title">Nothing is planned for today yet</h2>
          <p>
            Add a course source or create a task. Acadra explains what changed in each
            source and turns it into a step you can start, then places that step here.
          </p>
          <div className="page-actions">
            <Link className="submit-button" href="/sources/new">
              Add a source
            </Link>
            <Link className="connect-button" href="/tasks/new">
              New task
            </Link>
          </div>

          <p className="agenda-example-label">What a step looks like</p>
          <ol className="agenda" aria-label="Example agenda step">
            <li className="agenda-step current">
              <span className="agenda-index" aria-hidden="true">
                1
              </span>
              <div>
                <p className="agenda-action">Read the assignment brief</p>
                <p className="agenda-meta">
                  15 min · why now: due Thursday, and the brief decides the rest
                </p>
                <p className="agenda-source">
                  Course announcement · observed Mon 09:14 · due date changed
                </p>
              </div>
            </li>
          </ol>
        </div>
      </section>
    </div>
  );
}

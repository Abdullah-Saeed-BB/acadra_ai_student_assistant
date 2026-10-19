import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { TaskGroup } from "@/components/task-group";
import { TaskCreateButton } from "@/components/task-create";
import { formatDay } from "@/lib/format";
import { backendUnavailableMessage, getUpcomingPlan } from "@/lib/tasks";

export const metadata: Metadata = {
  title: "Upcoming",
};

function nextUtcDay(iso: string): string {
  const day = new Date(`${iso}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() + 1);
  return day.toISOString().slice(0, 10);
}

export default async function UpcomingPage() {
  let upcoming = null;
  let error: string | null = null;
  try {
    upcoming = await getUpcomingPlan(7);
  } catch (cause) {
    error =
      cause instanceof Error ? cause.message : backendUnavailableMessage();
  }

  const startDay = upcoming?.start_day ?? new Date().toISOString().slice(0, 10);

  return (
    <div className="page">
      <PageHeader
        title="Upcoming"
        description="Tasks selected for the next days, grouped by day.">
        <TaskCreateButton defaultDay={nextUtcDay(startDay)} />
      </PageHeader>

      {error ? (
        <section className="panel">
          <p className="message error" role="alert">
            {error}
          </p>
          <div className="page-actions">
            <Link className="connect-button" href="/">
              Back to Today
            </Link>
          </div>
        </section>
      ) : upcoming &&
        upcoming.days.every((group) => group.tasks.length === 0) ? (
        <section className="panel empty">
          <p className="panel-note">
            Nothing is scheduled for {upcoming.start_day} to {upcoming.end_day}{" "}
            yet. Choose a day for a backlog task to place it here.
          </p>
          <div className="page-actions">
            <Link className="page-link" href="/backlog">
              Review backlog
            </Link>
          </div>
        </section>
      ) : (
        <div className="upcoming-tasks">
          {upcoming?.days.map((group) => (
            <section
              key={group.day}
              className="panel"
              aria-labelledby={`day-${group.day}`}>
              <p className="panel-note">
                <span id={`day-${group.day}`}>
                  <span className="day-label">{formatDay(group.day)}</span> ·{" "}
                  {group.tasks.length}{" "}
                  {group.tasks.length === 1 ? "task" : "tasks"} ·{" "}
                  <span className="tnum">
                    {group.total_estimated_minutes} min
                  </span>
                </span>
              </p>
              {group.tasks.length > 0 ? (
                <TaskGroup tasks={group.tasks} />
              ) : (
                <p className="panel-note">No tasks selected for this day.</p>
              )}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

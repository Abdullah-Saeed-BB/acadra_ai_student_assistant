import Link from "next/link";
import type { ReactNode } from "react";
import type { Task } from "@/lib/tasks";

function effortLabel(minutes: number | null): string {
  return `${minutes ?? 0} min`;
}

function statusLabel(status: Task["status"]): string {
  if (status === "done") return "Done";
  if (status === "in_progress") return "In progress";
  return "To do";
}

/**
 * A single task rendered as its own container, so each fact gets room to
 * breathe. Today uses the compact container with clamped details; the task
 * detail page uses the large container and renders the full review surface.
 */
export function TaskCard({
  task,
  size = "default",
  detailsLines,
  linkTitle = true,
  showDay = true,
  titleAs: Heading = "h2",
  children,
}: {
  task: Task;
  size?: "default" | "large";
  /** Clamp the details to this many lines. Omit to show the full text. */
  detailsLines?: number;
  /** Link the title to the task detail page. Disable on the detail page itself. */
  linkTitle?: boolean;
  /** Show the selected day. Turn off when every task shares the same day. */
  showDay?: boolean;
  titleAs?: "h2" | "h3";
  /** Extra review facts (links, provenance) rendered inside the container. */
  children?: ReactNode;
}) {
  return (
    <article className={`task-card${size === "large" ? " task-card-large" : ""}`}>
      <div className="task-card-head">
        <Heading className="task-card-title">
          {linkTitle ? (
            <Link className="page-link" href={`/tasks/${task.id}`}>
              {task.title}
            </Link>
          ) : (
            task.title
          )}
        </Heading>
        <span className="task-card-status">{statusLabel(task.status)}</span>
      </div>

      {task.details ? (
        <p
          className={`task-card-details${detailsLines ? " is-clamped" : ""}`}
          style={detailsLines ? { WebkitLineClamp: detailsLines } : undefined}
        >
          {task.details}
        </p>
      ) : null}

      <dl className="task-card-meta">
        <div>
          <dt>Effort</dt>
          <dd className="tnum">{effortLabel(task.estimated_minutes)}</dd>
        </div>
        {showDay ? (
          <div>
            <dt>Day</dt>
            <dd>{task.selected_day ?? "Backlog"}</dd>
          </div>
        ) : null}
        {task.tags.length > 0 ? (
          <div>
            <dt>Tags</dt>
            <dd>{task.tags.join(", ")}</dd>
          </div>
        ) : null}
      </dl>

      {children}
    </article>
  );
}

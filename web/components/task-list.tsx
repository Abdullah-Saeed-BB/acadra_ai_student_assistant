import Link from "next/link";
import type { Task } from "@/lib/tasks";

function effortLabel(minutes: number | null): string {
  return `${minutes ?? 0} min`;
}

function statusLabel(status: Task["status"]): string {
  if (status === "done") return "Done";
  if (status === "in_progress") return "In progress";
  return "To do";
}

export function TaskList({ tasks }: { tasks: Task[] }) {
  if (tasks.length === 0) return null;
  return (
    <ol className="agenda" aria-label="Tasks">
      {tasks.map((task, index) => (
        <li key={task.id} className={`agenda-step${index === 0 ? " current" : ""}`}>
          <span className="agenda-index" aria-hidden="true">
            {index + 1}
          </span>
          <div>
            <p className="agenda-action">
              <Link className="page-link" href={`/tasks/${task.id}`}>
                {task.title}
              </Link>
            </p>
            <p className="agenda-meta">
              {effortLabel(task.estimated_minutes)} · {statusLabel(task.status)}
              {task.selected_day ? ` · ${task.selected_day}` : " · Backlog"}
              {task.tags.length ? ` · ${task.tags.join(", ")}` : ""}
            </p>
            {task.details ? <p className="agenda-source">{task.details}</p> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

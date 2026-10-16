"use client";

import Link from "next/link";
import type { Task } from "@/lib/tasks";
import {
  TaskActionNotice,
  TaskCheckButton,
  TaskDragHandle,
  TaskEditButton,
} from "@/components/task-actions";
import { useTaskReorder } from "@/components/use-task-reorder";

function effortLabel(minutes: number | null): string {
  return `${minutes ?? 0} min`;
}

function statusLabel(status: Task["status"]): string {
  if (status === "done") return "Done";
  if (status === "in_progress") return "In progress";
  return "To do";
}

/**
 * Shared agenda-style task list. Every row offers a check button to complete
 * the task and a pencil button to edit it. Only true top-level tasks get the
 * grip handle that reorders the list; sub-tasks stay in place here (they are
 * reordered on their parent's task detail page instead).
 */
export function TaskList({ tasks }: { tasks: Task[] }) {
  const reorder = useTaskReorder(
    tasks.map((task) => ({
      id: task.id,
      selectedDay: task.selected_day,
      canReorder: !task.parent_task_id,
    })),
  );

  if (tasks.length === 0) return null;

  const byId = new Map(tasks.map((task) => [task.id, task]));

  return (
    <>
      <ol
        className={`agenda${reorder.draggingId ? " is-dragging" : ""}`}
        aria-label="Tasks"
        {...reorder.containerProps}>
        {reorder.order.map((id, index) => {
          const task = byId.get(id);
          if (!task) return null;
          const draggable = !task.parent_task_id;
          return (
            <li
              key={id}
              className={`agenda-step${index === 0 ? " current" : ""}${
                task.status === "done" ? " is-done" : ""
              }${reorder.draggingId === id ? " is-dragging" : ""}`}
              {...reorder.itemProps(id)}>
              {draggable ? (
                <TaskDragHandle
                  className={`task-drag-handle agenda-handle${
                    reorder.armedId === id ? " is-armed" : ""
                  }`}
                  handleProps={reorder.handleProps(id)}
                />
              ) : (
                <span className="agenda-handle agenda-handle-space" aria-hidden="true" />
              )}
              <TaskCheckButton task={task} index={index} />
              <div>
                <p className="agenda-action">
                  {task.parent_task_id ? (
                    task.title
                  ) : (
                    <Link className="page-link" href={`/tasks/${task.id}`}>
                      {task.title}
                    </Link>
                  )}
                </p>
                <p className="agenda-meta">
                  {effortLabel(task.estimated_minutes)} ·{" "}
                  {statusLabel(task.status)}
                  {task.selected_day ? ` · ${task.selected_day}` : " · Backlog"}
                  {task.tags.length ? ` · ${task.tags.join(", ")}` : ""}
                </p>
                {task.details ? (
                  <p className="agenda-source">{task.details}</p>
                ) : null}
              </div>
              <TaskEditButton task={task} />
            </li>
          );
        })}
      </ol>
      <TaskActionNotice
        message={reorder.error}
        onDismiss={reorder.clearError}
      />
    </>
  );
}

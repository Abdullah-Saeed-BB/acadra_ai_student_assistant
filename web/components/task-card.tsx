"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { DragEvent, ReactNode } from "react";
import type { Task, TaskDetail } from "@/lib/tasks";
import { loadTaskOptions } from "@/lib/task-options";
import type { TaskOptions } from "@/lib/task-options";
import {
  TaskCheckButton,
  TaskDeleteButton,
  TaskDragHandle,
  TaskEditButton,
} from "@/components/task-actions";

function effortLabel(minutes: number | null): string {
  return `${minutes ?? 0} min`;
}

function statusLabel(status: Task["status"]): string {
  if (status === "done") return "Done";
  if (status === "in_progress") return "In progress";
  return "To do";
}

let optionsCache: TaskOptions | null = null;
let optionsPromise: Promise<TaskOptions> | null = null;

function getTaskOptionsCached(): Promise<TaskOptions> {
  if (optionsCache) return Promise.resolve(optionsCache);
  if (!optionsPromise) {
    optionsPromise = loadTaskOptions()
      .then((opts) => {
        optionsCache = opts;
        return opts;
      })
      .catch((err) => {
        optionsPromise = null;
        throw err;
      });
  }
  return optionsPromise;
}

/** Drag wiring supplied by `useTaskReorder` for a reorderable container. */
export type TaskCardDrag = {
  handleProps: { onMouseDown: () => void };
  itemProps: {
    draggable: boolean;
    onDragStart: (event: DragEvent<HTMLElement>) => void;
    onDragEnd: (event: DragEvent<HTMLElement>) => void;
    onDragOver: (event: DragEvent<HTMLElement>) => void;
  };
  dragging: boolean;
  armed: boolean;
};

/**
 * A single task rendered as its own container, so each fact gets room to
 * breathe. Today uses the compact container with clamped details; the task
 * detail page uses the large container and renders the full review surface.
 *
 * Every container offers a check button to complete the task, a pencil
 * button to edit it, and a trash button that deletes it behind a confirm
 * dialog listing any steps the deletion would take. Containers passed `drag`
 * wiring also show the grip handle that reorders the task in its list.
 */
export function TaskCard({
  task,
  size = "default",
  detailsLines,
  linkTitle = true,
  showDay = true,
  titleAs: Heading = "h2",
  steps,
  children,
  drag,
}: {
  task: Task;
  size?: "default" | "large" | "nested";
  /** Clamp the details to this many lines. Omit to show the full text. */
  detailsLines?: number;
  /** Link the title to the task detail page. Disable on the detail page itself. */
  linkTitle?: boolean;
  /** Show the selected day. Turn off when every task shares the same day. */
  showDay?: boolean;
  titleAs?: "h2" | "h3";
  /** Step tasks nested inside this task's container. */
  steps?: Task[];
  /** Extra review facts (links, provenance) rendered inside the container. */
  children?: ReactNode;
  /** Drag wiring for reorderable lists. Steps and detail views omit it. */
  drag?: TaskCardDrag;
}) {
  // Steps live inside their top-level task and have no detail page, so they are
  // never linked even when the surrounding list opts into linked titles.
  const titleIsLink = linkTitle && !task.parent_task_id;

  const [options, setOptions] = useState<TaskOptions | null>(optionsCache);
  useEffect(() => {
    let active = true;
    if (optionsCache) {
      setOptions(optionsCache);
      return () => {
        active = false;
      };
    }
    getTaskOptionsCached()
      .then((opts) => {
        if (active) setOptions(opts);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const detailTask = task as unknown as TaskDetail;
  const resolvedAcademic =
    detailTask.academic_item ??
    (task.academic_item_id && options
      ? (() => {
          const found = options.academic_items.find(
            (item) => item.id === task.academic_item_id,
          );
          return found
            ? {
                id: found.id,
                title: found.title,
                item_type: found.item_type,
                due_at: found.due_at,
              }
            : null;
        })()
      : null);
  const resolvedCourse =
    detailTask.course ??
    (task.course_id && options
      ? (() => {
          const found = options.courses.find(
            (course) => course.id === task.course_id,
          );
          return found
            ? { id: found.id, code: found.code, name: found.name }
            : null;
        })()
      : null);

  const sizeClass =
    size === "large" ? " task-card-large" : size === "nested" ? " is-nested" : "";

  return (
    <article
      className={`task-card${sizeClass}${task.status === "done" ? " is-done" : ""}${drag?.dragging ? " is-dragging" : ""}`}
      {...(drag ? drag.itemProps : {})}>
      <div className="task-card-head">
        {drag ? (
          <TaskDragHandle
            className={`task-drag-handle${drag.armed ? " is-armed" : ""}`}
            handleProps={drag.handleProps}
          />
        ) : null}
        <TaskCheckButton task={task} />
        <Heading className="task-card-title">
          {titleIsLink ? (
            <Link className="page-link" href={`/tasks/${task.id}`}>
              {task.title}
            </Link>
          ) : (
            task.title
          )}
        </Heading>
        <span className={`task-card-status task-card-status-${task.status === "done" ? "done" : "todo"}`}>{statusLabel(task.status)}</span>
        <TaskEditButton task={task} />
        <TaskDeleteButton task={task} />
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
        {resolvedAcademic ? (
          <>
            <div>
              <dt>Academic item</dt>
              <dd>
                <Link className="page-link" href={`/items/${resolvedAcademic.id}`}>
                  {resolvedAcademic.title}
                </Link>
              </dd>
            </div>
            {resolvedAcademic.item_type ? (
              <div>
                <dt>Type</dt>
                <dd>{resolvedAcademic.item_type}</dd>
              </div>
            ) : null}
            {resolvedAcademic.due_at ? (
              <div>
                <dt>Due</dt>
                <dd className="tnum">{resolvedAcademic.due_at}</dd>
              </div>
            ) : null}
          </>
        ) : null}
        {resolvedCourse ? (
          <div>
            <dt>Course</dt>
            <dd>
              {resolvedCourse.code ? `${resolvedCourse.code} · ` : ""}
              {resolvedCourse.name}
            </dd>
          </div>
        ) : null}
      </dl>

      {children}

      {steps && steps.length > 0 ? (
        <div className="task-card-steps">
          {steps.map((step) => (
            <TaskCard
              key={step.id}
              task={step}
              size="nested"
              titleAs="h3"
              detailsLines={detailsLines}
              showDay={showDay}
            />
          ))}
        </div>
      ) : null}
    </article>
  );
}

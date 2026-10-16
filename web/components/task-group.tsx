"use client";

import { TaskCard } from "@/components/task-card";
import { TaskActionNotice } from "@/components/task-actions";
import { useTaskReorder } from "@/components/use-task-reorder";
import type { Task } from "@/lib/tasks";

/**
 * Renders a list of tasks as containers, nesting each top-level task's step
 * tasks inside the parent's container instead of giving every step its own
 * top-level container. A step whose parent is not in the list stays a top-level
 * container so unscheduled parents never hide their steps.
 *
 * Containers can be reordered with their drag handle; the new order is saved
 * for that day's list. By default only true top-level tasks are reorderable —
 * pass `allowStepReorder` to also reorder the steps themselves, as the task
 * detail page does for the steps under one parent.
 */
export function TaskGroup({
  tasks,
  detailsLines,
  showDay,
  titleAs,
  allowStepReorder = false,
}: {
  tasks: Task[];
  /** Clamp each task's details to this many lines. Omit to show the full text. */
  detailsLines?: number;
  /** Show the selected day on each container. */
  showDay?: boolean;
  /** Heading level for each container's title. */
  titleAs?: "h2" | "h3";
  /** Let sub-tasks be reordered too (the task detail page's step list). */
  allowStepReorder?: boolean;
}) {
  const byId = new Map(tasks.map((task) => [task.id, task]));
  const roots: Task[] = [];
  const stepsByParent = new Map<string, Task[]>();

  for (const task of tasks) {
    const parentId = task.parent_task_id;
    if (parentId && byId.has(parentId)) {
      const steps = stepsByParent.get(parentId) ?? [];
      steps.push(task);
      stepsByParent.set(parentId, steps);
    } else {
      roots.push(task);
    }
  }

  const reorder = useTaskReorder(
    roots.map((task) => ({
      id: task.id,
      selectedDay: task.selected_day,
      canReorder: allowStepReorder || !task.parent_task_id,
    })),
  );

  return (
    <>
      <div
        className={`task-cards${reorder.draggingId ? " is-dragging" : ""}`}
        {...reorder.containerProps}>
        {reorder.order.map((id) => {
          const task = byId.get(id);
          if (!task) return null;
          const reorderable = allowStepReorder || !task.parent_task_id;
          return (
            <TaskCard
              key={id}
              task={task}
              titleAs={titleAs}
              detailsLines={detailsLines}
              showDay={showDay}
              steps={stepsByParent.get(id)}
              drag={
                reorderable
                  ? {
                      handleProps: reorder.handleProps(id),
                      itemProps: reorder.itemProps(id),
                      dragging: reorder.draggingId === id,
                      armed: reorder.armedId === id,
                    }
                  : undefined
              }
            />
          );
        })}
      </div>
      <TaskActionNotice
        message={reorder.error}
        onDismiss={reorder.clearError}
      />
    </>
  );
}

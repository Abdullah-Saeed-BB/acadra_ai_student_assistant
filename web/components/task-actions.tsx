"use client";

import { FormEvent, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { usePathname, useRouter } from "next/navigation";
import type { Task } from "@/lib/tasks";
import type { TaskDragHandleProps } from "@/components/use-task-reorder";
import { loadTaskOptions, type TaskOptions } from "@/lib/task-options";

/** The grip icon shown on the drag handle beside a task. */
function GripIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true">
      <circle cx="9" cy="6" r="1.6" />
      <circle cx="15" cy="6" r="1.6" />
      <circle cx="9" cy="12" r="1.6" />
      <circle cx="15" cy="12" r="1.6" />
      <circle cx="9" cy="18" r="1.6" />
      <circle cx="15" cy="18" r="1.6" />
    </svg>
  );
}

/** The tick shown when a task is done. */
function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true">
      <path d="m5 12.5 4.5 4.5L19 7" />
    </svg>
  );
}

/** The pencil icon on the edit button. */
function PencilIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

/** The trash icon on the delete button. */
function TrashIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true">
      <path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13" />
      <path d="M10 11v6M14 11v6" />
    </svg>
  );
}

/**
 * A floating notice for a failed task action. It sits above the list so a
 * failed save nearby can never break the surrounding layout.
 */
export function TaskActionNotice({
  message,
  onDismiss,
}: {
  message: string | null;
  onDismiss?: () => void;
}) {
  const dismissRef = useRef(onDismiss);

  useEffect(() => {
    dismissRef.current = onDismiss;
  });

  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(() => dismissRef.current?.(), 6000);
    return () => window.clearTimeout(timer);
  }, [message]);

  if (!message || typeof document === "undefined") return null;

  return createPortal(
    <div className="task-toast" role="alert">
      <span>{message}</span>
      <button
        type="button"
        className="task-toast-close"
        aria-label="Dismiss"
        onClick={() => dismissRef.current?.()}>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          aria-hidden="true">
          <path d="m6 6 12 12M18 6 6 18" />
        </svg>
      </button>
    </div>,
    document.body,
  );
}

/**
 * The check button that completes a task, or returns a completed task to the
 * todo list. Used both as the plain circle on task containers and, with an
 * index, as the numbered circle in the agenda list.
 *
 * Remounting on status changes keeps the optimistic local state honest: when
 * the refresh delivers the saved task, the button starts from the server
 * value again.
 */
export function TaskCheckButton({
  task,
  index,
}: {
  task: Task;
  /** Position in the list, shown inside the circle until the task is done. */
  index?: number;
}) {
  return <TaskCheckButtonState key={task.status} task={task} index={index} />;
}

function TaskCheckButtonState({
  task,
  index,
}: {
  task: Task;
  index?: number;
}) {
  const router = useRouter();
  const [done, setDone] = useState(task.status === "done");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    if (busy) return;
    const nextDone = !done;
    // Switch immediately; the refresh confirms the saved state.
    setDone(nextDone);
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/tasks/${encodeURIComponent(task.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextDone ? "done" : "todo" }),
      });
      const data = (await response.json()) as { error?: string };
      if (!response.ok) {
        throw new Error(data.error || "The task could not be updated.");
      }
      router.refresh();
    } catch (cause) {
      setDone(!nextDone);
      setError(
        cause instanceof Error
          ? cause.message
          : "The task could not be updated.",
      );
    } finally {
      setBusy(false);
    }
  }

  const numbered = index !== undefined;
  const className = [
    numbered ? "agenda-index agenda-check" : "task-check",
    done ? "is-done" : "",
    numbered && index === 0 ? "current" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <>
      <button
        type="button"
        className={className}
        aria-pressed={done}
        aria-label={
          done
            ? `Mark ${task.title} as not done`
            : `Mark ${task.title} as done`
        }
        title={done ? "Mark as not done" : "Mark as done"}
        disabled={busy}
        onClick={toggle}>
        {done ? (
          <CheckIcon />
        ) : numbered ? (
          <span aria-hidden="true">{index + 1}</span>
        ) : (
          <CheckIcon className="task-check-hint" />
        )}
      </button>
      <TaskActionNotice message={error} onDismiss={() => setError(null)} />
    </>
  );
}

/** The grip button shown beside a task; drag it to reorder the task. */
export function TaskDragHandle({
  className,
  handleProps,
}: {
  className: string;
  handleProps: TaskDragHandleProps;
}) {
  return (
    <button
      type="button"
      className={className}
      aria-label="Drag to reorder"
      title="Drag to reorder"
      {...handleProps}>
      <GripIcon />
    </button>
  );
}

type EditForm = {
  title: string;
  details: string;
  day: string;
  minutes: string;
  tags: string;
  academicItemId: string;
  courseId: string;
};

function formFromTask(task: Task): EditForm {
  return {
    title: task.title,
    details: task.details ?? "",
    day: task.selected_day ?? "",
    minutes:
      task.estimated_minutes !== null ? String(task.estimated_minutes) : "",
    tags: task.tags.join(", "),
    academicItemId: task.academic_item_id ?? "",
    courseId: task.course_id ?? "",
  };
}

/**
 * The pencil button that opens a dialog for editing a task's information:
 * title, details, selected day, estimated effort, tags, and the linked
 * academic item and course. Saving patches the task through the backend and
 * refreshes the surrounding list in place.
 */
export function TaskEditButton({ task }: { task: Task }) {
  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<EditForm>(() => formFromTask(task));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [options, setOptions] = useState<TaskOptions | null>(null);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [optionsError, setOptionsError] = useState<string | null>(null);

  // Keep the native dialog in sync with React state so Escape, the close
  // button, and successful saves all share one source of truth.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open]);

  function openDialog() {
    setForm(formFromTask(task));
    setError(null);
    setBusy(false);
    setOpen(true);
    void loadOptions();
  }

  async function loadOptions() {
    if (options || optionsLoading) return;
    setOptionsLoading(true);
    setOptionsError(null);
    try {
      setOptions(await loadTaskOptions());
    } catch (cause) {
      setOptionsError(
        cause instanceof Error
          ? cause.message
          : "Could not load academic items and courses.",
      );
    } finally {
      setOptionsLoading(false);
    }
  }

  function closeDialog() {
    if (busy) return;
    setOpen(false);
  }

  function update<K extends keyof EditForm>(key: K, value: EditForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const title = form.title.trim();
    if (!title) {
      setError("Enter a task title.");
      return;
    }

    const tagList = form.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
    if (tagList.length > 10) {
      setError("Use at most 10 tags.");
      return;
    }
    if (tagList.some((tag) => tag.length > 50)) {
      setError("Each tag must be 50 characters or fewer.");
      return;
    }

    let estimatedMinutes: number | null = null;
    if (form.minutes.trim()) {
      const parsed = Number(form.minutes);
      if (!Number.isInteger(parsed) || parsed < 1 || parsed > 1440) {
        setError("Estimated effort must be between 1 and 1440 minutes.");
        return;
      }
      estimatedMinutes = parsed;
    }

    const body: Record<string, unknown> = {
      title,
      details: form.details.trim(),
      selected_day: form.day || null,
      tags: tagList,
      // Sent explicitly every time: a value links, null unlinks, and the
      // form seeds from the task, so an untouched field re-sends its current id.
      academic_item_id: form.academicItemId || null,
      course_id: form.courseId || null,
    };
    if (estimatedMinutes !== null) body.estimated_minutes = estimatedMinutes;
    else body.clear_estimated_minutes = true;

    setBusy(true);
    try {
      const response = await fetch(`/api/tasks/${encodeURIComponent(task.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data: { error?: string; details?: { message: string }[] } =
        await response.json();
      if (!response.ok) {
        throw new Error(
          data.details?.[0]?.message ||
            data.error ||
            "The task could not be updated.",
        );
      }
      setOpen(false);
      router.refresh();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "The task could not be updated.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className="task-edit"
        aria-label={`Edit ${task.title}`}
        title="Edit task"
        onClick={openDialog}>
        <PencilIcon />
      </button>

      <dialog
        ref={dialogRef}
        className="task-dialog"
        aria-labelledby={titleId}
        onClose={() => setOpen(false)}
        onClick={(event) => {
          if (event.target === dialogRef.current) closeDialog();
        }}>
        <div className="task-dialog-head">
          <h2 id={titleId}>Edit task</h2>
          <button
            type="button"
            className="task-dialog-close"
            aria-label="Close"
            onClick={closeDialog}>
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              aria-hidden="true">
              <path d="m6 6 12 12M18 6 6 18" />
            </svg>
          </button>
        </div>

        <form className="task-dialog-body" onSubmit={submit}>
          <div className="field">
            <label htmlFor={`${titleId}-title`}>Title</label>
            <input
              id={`${titleId}-title`}
              type="text"
              value={form.title}
              maxLength={200}
              autoFocus
              disabled={busy}
              onChange={(event) => update("title", event.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor={`${titleId}-details`}>
              Details <span className="optional">optional</span>
            </label>
            <textarea
              id={`${titleId}-details`}
              value={form.details}
              maxLength={2000}
              placeholder="What exactly needs to happen?"
              rows={3}
              disabled={busy}
              onChange={(event) => update("details", event.target.value)}
            />
          </div>

          <div className="task-form-row">
            <div className="field">
              <label htmlFor={`${titleId}-day`}>
                Selected day <span className="optional">optional</span>
              </label>
              <input
                id={`${titleId}-day`}
                type="date"
                value={form.day}
                disabled={busy}
                onChange={(event) => update("day", event.target.value)}
              />
              <p className="field-hint">
                Leave empty to send it to the Backlog.
              </p>
            </div>

            <div className="field">
              <label htmlFor={`${titleId}-minutes`}>
                Effort <span className="optional">optional</span>
              </label>
              <input
                id={`${titleId}-minutes`}
                type="number"
                min={0}
                max={1440}
                step={5}
                value={form.minutes}
                placeholder="minutes"
                disabled={busy}
                onChange={(event) => update("minutes", event.target.value)}
              />
              <p className="field-hint">Estimated minutes (0–1440).</p>
            </div>
          </div>

          <div className="task-form-row">
            <div className="field">
              <label htmlFor={`${titleId}-item`}>
                Academic item <span className="optional">optional</span>
              </label>
              <select
                id={`${titleId}-item`}
                value={form.academicItemId}
                disabled={busy || optionsLoading}
                onChange={(event) =>
                  update("academicItemId", event.target.value)
                }>
                <option value="">None linked</option>
                {form.academicItemId &&
                !(options?.academic_items ?? []).some(
                  (item) => item.id === form.academicItemId,
                ) ? (
                  <option value={form.academicItemId}>
                    Linked academic item
                  </option>
                ) : null}
                {(options?.academic_items ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title}
                    {item.due_at ? ` · ${item.due_at.slice(0, 10)}` : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label htmlFor={`${titleId}-course`}>
                Course <span className="optional">optional</span>
              </label>
              <select
                id={`${titleId}-course`}
                value={form.courseId}
                disabled={busy || optionsLoading}
                onChange={(event) => update("courseId", event.target.value)}>
                <option value="">None linked</option>
                {form.courseId &&
                !(options?.courses ?? []).some(
                  (course) => course.id === form.courseId,
                ) ? (
                  <option value={form.courseId}>Linked course</option>
                ) : null}
                {(options?.courses ?? []).map((course) => (
                  <option key={course.id} value={course.id}>
                    {course.code ? `${course.code} · ` : ""}
                    {course.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {optionsLoading ? (
            <p className="field-hint">Loading academic items and courses…</p>
          ) : null}
          {optionsError ? (
            <p className="field-hint" role="alert">
              {optionsError}
            </p>
          ) : null}

          <div className="field">
            <label htmlFor={`${titleId}-tags`}>
              Tags <span className="optional">optional</span>
            </label>
            <input
              id={`${titleId}-tags`}
              type="text"
              value={form.tags}
              placeholder="math, homework"
              disabled={busy}
              onChange={(event) => update("tags", event.target.value)}
            />
            <p className="field-hint">Comma-separated, up to 10 tags.</p>
          </div>

          {error && (
            <p className="message error" role="alert">
              {error}
            </p>
          )}

          <div className="task-dialog-actions">
            <button className="submit-button" type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save changes"}
            </button>
            <button
              type="button"
              className="connect-button"
              disabled={busy}
              onClick={closeDialog}>
              Cancel
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

/**
 * The trash button that deletes a task, behind a confirm dialog that warns
 * the deletion is permanent. While the dialog opens it asks the task service
 * which steps belong to the task; if any exist, the warning lists them by
 * title because deleting a task deletes its steps with it.
 *
 * The destructive button stays unavailable until that check succeeds, so a
 * deletion can never run without the user having seen what it takes. A task
 * deleted from its own detail page navigates back to the list instead of
 * refreshing a route that is now a 404.
 */
export function TaskDeleteButton({ task }: { task: Task }) {
  const router = useRouter();
  const pathname = usePathname();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [steps, setSteps] = useState<Task[] | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Keep the native dialog in sync with React state so Escape, the close
  // button, and a finished delete all share one source of truth.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open]);

  function openDialog() {
    setError(null);
    setBusy(false);
    setOpen(true);
    void checkSteps();
  }

  function closeDialog() {
    if (busy) return;
    setOpen(false);
  }

  async function checkSteps() {
    setChecking(true);
    setCheckError(null);
    setSteps(null);
    try {
      const response = await fetch(`/api/tasks/${encodeURIComponent(task.id)}`);
      const data = (await response.json()) as { steps?: Task[]; error?: string };
      if (!response.ok) {
        throw new Error(data.error || "The task service did not respond.");
      }
      setSteps(data.steps ?? []);
    } catch (cause) {
      setCheckError(
        cause instanceof Error
          ? cause.message
          : "The task service did not respond.",
      );
    } finally {
      setChecking(false);
    }
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/tasks/${encodeURIComponent(task.id)}`, {
        method: "DELETE",
      });
      const data = (await response.json()) as { error?: string };
      if (!response.ok) {
        throw new Error(data.error || "The task could not be deleted.");
      }
      setOpen(false);
      // This task's detail route is a 404 now, so leave it before refreshing.
      if (pathname === `/tasks/${task.id}`) {
        router.push("/tasks");
        router.refresh();
      } else {
        router.refresh();
      }
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "The task could not be deleted.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className="task-delete"
        aria-label={`Delete ${task.title}`}
        title="Delete task"
        onClick={openDialog}>
        <TrashIcon />
      </button>

      <dialog
        ref={dialogRef}
        className="task-dialog task-dialog-compact"
        aria-labelledby={titleId}
        onClose={() => setOpen(false)}
        onClick={(event) => {
          if (event.target === dialogRef.current) closeDialog();
        }}>
        <div className="task-dialog-head">
          <h2 id={titleId}>Delete task?</h2>
          <button
            type="button"
            className="task-dialog-close"
            aria-label="Close"
            onClick={closeDialog}>
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              aria-hidden="true">
              <path d="m6 6 12 12M18 6 6 18" />
            </svg>
          </button>
        </div>

        <div className="task-dialog-body">
          <p className="panel-note">
            “{task.title}” will be deleted permanently. This cannot be undone.
          </p>

          {checking ? (
            <p className="panel-note" role="status">
              Checking for steps…
            </p>
          ) : checkError ? (
            <p className="message error" role="alert">
              Could not list this task’s steps, so nothing can be deleted yet.{" "}
              {checkError}
            </p>
          ) : steps && steps.length > 0 ? (
            <div className="task-delete-cascade">
              <p>
                This task has{" "}
                {steps.length === 1
                  ? "1 step that"
                  : `${steps.length} steps that`}{" "}
                will be deleted with it:
              </p>
              <ul className="task-delete-steps">
                {steps.map((step) => (
                  <li key={step.id}>{step.title}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {error ? (
            <p className="message error" role="alert">
              {error}
            </p>
          ) : null}

          <div className="task-dialog-actions">
            {checkError ? (
              <button
                type="button"
                className="submit-button"
                disabled={checking}
                onClick={() => void checkSteps()}>
                Check again
              </button>
            ) : (
              <button
                type="button"
                className="submit-button is-danger"
                disabled={busy || checking || steps === null}
                onClick={() => void confirm()}>
                {busy ? "Deleting…" : "Delete task"}
              </button>
            )}
            <button
              type="button"
              className="connect-button"
              disabled={busy}
              onClick={closeDialog}>
              Cancel
            </button>
          </div>
        </div>
      </dialog>
    </>
  );
}

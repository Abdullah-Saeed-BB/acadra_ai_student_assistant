"use client";

import { FormEvent, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import type { Task } from "@/lib/tasks";

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

/** The grip button shown beside a task; press and drag to reorder it. */
export function TaskDragHandle({
  className,
  handleProps,
}: {
  className: string;
  handleProps: { onMouseDown: () => void };
}) {
  return (
    <button
      type="button"
      className={className}
      aria-label="Drag to reorder"
      title="Hold and drag to reorder"
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
};

function formFromTask(task: Task): EditForm {
  return {
    title: task.title,
    details: task.details ?? "",
    day: task.selected_day ?? "",
    minutes:
      task.estimated_minutes !== null ? String(task.estimated_minutes) : "",
    tags: task.tags.join(", "),
  };
}

/**
 * The pencil button that opens a dialog for editing a task's information:
 * title, details, selected day, estimated effort, and tags. Saving patches the
 * task through the backend and refreshes the surrounding list in place.
 */
export function TaskEditButton({ task }: { task: Task }) {
  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<EditForm>(() => formFromTask(task));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

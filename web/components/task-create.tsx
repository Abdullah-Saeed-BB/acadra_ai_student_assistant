"use client";

import { FormEvent, useEffect, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";

type NewTask = {
  title: string;
  details: string;
  day: string;
  minutes: string;
  tags: string;
  academicItemId: string;
  courseId: string;
};

type AcademicItemOption = {
  id: string;
  title: string;
  item_type: string;
  due_at: string | null;
};

type CourseOption = {
  id: string;
  code: string | null;
  name: string;
  term: string | null;
};

type TaskOptions = {
  academic_items: AcademicItemOption[];
  courses: CourseOption[];
};

function emptyForm(defaultDay: string): NewTask {
  return {
    title: "",
    details: "",
    day: defaultDay,
    minutes: "",
    tags: "",
    academicItemId: "",
    courseId: "",
  };
}

/**
 * "New task" button plus a modal form. Used on the plan and task views so a
 * task can be created without leaving the current list. `defaultDay` seeds the
 * selected-day field: Today passes the plan's day, Upcoming passes tomorrow,
 * and the all-tasks view leaves it empty for the student to fill in.
 *
 * Pass `parentTaskId` to create a child step: the backend links the new task to
 * that parent and inherits the parent's academic-item and course links.
 */
export function TaskCreateButton({
  defaultDay = "",
  label = "New task",
  heading = "New task",
  submitLabel = "Create task",
  parentTaskId,
}: {
  defaultDay?: string;
  label?: string;
  /** Dialog heading. */
  heading?: string;
  /** Submit button text. */
  submitLabel?: string;
  /** Create the new task as a child step of this task. */
  parentTaskId?: string;
}) {
  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<NewTask>(() => emptyForm(defaultDay));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [options, setOptions] = useState<TaskOptions | null>(null);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [optionsError, setOptionsError] = useState<string | null>(null);

  // Keep the native dialog in sync with React state so Escape, the close
  // button, and successful submits all share one source of truth.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open]);

  function openDialog() {
    setForm(emptyForm(defaultDay));
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
      const response = await fetch("/api/task-options", { cache: "no-store" });
      const data = (await response.json()) as {
        academic_items?: AcademicItemOption[];
        courses?: CourseOption[];
        error?: string;
      };
      if (!response.ok) {
        throw new Error(
          data.error || "Could not load academic items and courses.",
        );
      }
      setOptions({
        academic_items: data.academic_items ?? [],
        courses: data.courses ?? [],
      });
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

  function update<K extends keyof NewTask>(key: K, value: NewTask[K]) {
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

    setBusy(true);
    try {
      const response = await fetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          ...(form.details.trim() ? { details: form.details.trim() } : {}),
          selected_day: form.day || null,
          estimated_minutes: estimatedMinutes,
          tags: tagList,
          ...(parentTaskId ? { parent_task_id: parentTaskId } : {}),
          ...(form.academicItemId
            ? { academic_item_id: form.academicItemId }
            : {}),
          ...(form.courseId ? { course_id: form.courseId } : {}),
        }),
      });
      const data: { error?: string; details?: { message: string }[] } =
        await response.json();
      if (!response.ok) {
        throw new Error(
          data.details?.[0]?.message ||
            data.error ||
            "The task could not be created.",
        );
      }
      setOpen(false);
      router.refresh();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "The task could not be created.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" className="submit-button" onClick={openDialog}>
        {label}
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
          <h2 id={titleId}>{heading}</h2>
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
              placeholder="e.g. Read Physics chapter 3"
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

          {/* <div className="task-form-row">
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
              AAA{optionsError}
            </p>
          ) : null} */}

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
              {busy ? "Creating…" : submitLabel}
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

"use client";

import {
  FormEvent,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { useRouter } from "next/navigation";
import type {
  AcademicItem,
  AcademicItemType,
  Course,
  ReviewState,
} from "@/lib/academics";

const ITEM_TYPES: AcademicItemType[] = [
  "assignment",
  "announcement",
  "reading",
  "event",
];

const REVIEW_STATES: ReviewState[] = ["verified", "uncertain", "conflicting"];

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

function CloseIcon() {
  return (
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
  );
}

function isoToLocalInput(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

function localInputToIso(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function parseError(data: {
  error?: string;
  details?: { message: string }[];
}): string {
  return (
    data.details?.[0]?.message || data.error || "The change could not be saved."
  );
}

/** Shared native-dialog plumbing so Escape, backdrop, and saves agree. */
function useDialog(open: boolean, ref: RefObject<HTMLDialogElement | null>) {
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open, ref]);
}

// ---------------------------------------------------------------- courses --

type CourseForm = { name: string; code: string; term: string };

function CourseDialogButton({
  course,
  trigger,
}: {
  course?: Course;
  trigger: (open: () => void) => ReactNode;
}) {
  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<CourseForm>({
    name: course?.name ?? "",
    code: course?.code ?? "",
    term: course?.term ?? "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useDialog(open, dialogRef);

  function openDialog() {
    setForm({
      name: course?.name ?? "",
      code: course?.code ?? "",
      term: course?.term ?? "",
    });
    setError(null);
    setBusy(false);
    setOpen(true);
  }

  function close() {
    if (busy) return;
    setOpen(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = form.name.trim();
    if (!name) {
      setError("Enter a course name.");
      return;
    }
    const code = form.code.trim();
    const term = form.term.trim();

    const body: Record<string, unknown> = { name };
    if (course) {
      if (code) body.code = code;
      else body.clear_code = true;
      if (term) body.term = term;
      else body.clear_term = true;
    } else {
      body.code = code || null;
      body.term = term || null;
    }

    setBusy(true);
    setError(null);
    try {
      const endpoint = course
        ? `/api/courses/${encodeURIComponent(course.id)}`
        : "/api/courses";
      const response = await fetch(endpoint, {
        method: course ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = (await response.json()) as {
        error?: string;
        details?: { message: string }[];
      };
      if (!response.ok) throw new Error(parseError(data));
      setOpen(false);
      router.refresh();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "The course could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {trigger(openDialog)}
      <dialog
        ref={dialogRef}
        className="task-dialog"
        aria-labelledby={titleId}
        onClose={() => setOpen(false)}
        onClick={(event) => {
          if (event.target === dialogRef.current) close();
        }}>
        <div className="task-dialog-head">
          <h2 id={titleId}>{course ? "Edit course" : "New course"}</h2>
          <button
            type="button"
            className="task-dialog-close"
            aria-label="Close"
            onClick={close}>
            <CloseIcon />
          </button>
        </div>
        <form className="task-dialog-body" onSubmit={submit}>
          <div className="field">
            <label htmlFor={`${titleId}-name`}>Name</label>
            <input
              id={`${titleId}-name`}
              type="text"
              value={form.name}
              maxLength={200}
              autoFocus
              disabled={busy}
              placeholder="e.g. Linear Algebra"
              onChange={(event) =>
                setForm({ ...form, name: event.target.value })
              }
            />
          </div>
          <div className="task-form-row">
            <div className="field">
              <label htmlFor={`${titleId}-code`}>
                Code <span className="optional">optional</span>
              </label>
              <input
                id={`${titleId}-code`}
                type="text"
                value={form.code}
                maxLength={50}
                disabled={busy}
                placeholder="MATH 221"
                onChange={(event) =>
                  setForm({ ...form, code: event.target.value })
                }
              />
            </div>
            <div className="field">
              <label htmlFor={`${titleId}-term`}>
                Term <span className="optional">optional</span>
              </label>
              <input
                id={`${titleId}-term`}
                type="text"
                value={form.term}
                maxLength={100}
                disabled={busy}
                placeholder="Fall 2026"
                onChange={(event) =>
                  setForm({ ...form, term: event.target.value })
                }
              />
            </div>
          </div>
          {error ? (
            <p className="message error" role="alert">
              {error}
            </p>
          ) : null}
          <div className="task-dialog-actions">
            <button className="submit-button" type="submit" disabled={busy}>
              {busy ? "Saving…" : course ? "Save changes" : "Create course"}
            </button>
            <button
              type="button"
              className="connect-button"
              disabled={busy}
              onClick={close}>
              Cancel
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

export function CourseCreateButton() {
  return (
    <CourseDialogButton
      trigger={(open) => (
        <button type="button" className="submit-button" onClick={open}>
          New course
        </button>
      )}
    />
  );
}

export function CourseEditButton({ course }: { course: Course }) {
  return (
    <CourseDialogButton
      course={course}
      trigger={(open) => (
        <button
          type="button"
          className="icon-button"
          aria-label={`Edit ${course.name}`}
          title="Edit course"
          onClick={open}>
          <PencilIcon />
        </button>
      )}
    />
  );
}

// --------------------------------------------------------- academic items --

type ItemForm = {
  itemType: AcademicItemType;
  title: string;
  details: string;
  courseId: string;
  startsAt: string;
  dueAt: string;
  weight: string;
  penalty: string;
  reviewState: ReviewState;
};

function formFromItem(item?: AcademicItem, defaultCourseId = ""): ItemForm {
  return {
    itemType: item?.item_type ?? "assignment",
    title: item?.title ?? "",
    details: item?.details ?? "",
    courseId: item?.course_id ?? defaultCourseId,
    startsAt: isoToLocalInput(item?.starts_at ?? null),
    dueAt: isoToLocalInput(item?.due_at ?? null),
    weight:
      item?.grade_weight_percent !== null &&
      item?.grade_weight_percent !== undefined
        ? String(item.grade_weight_percent)
        : "",
    penalty: item?.late_penalty ?? "",
    reviewState: item?.review_state ?? "verified",
  };
}

function ItemDialogButton({
  item,
  courses,
  defaultCourseId = "",
  trigger,
}: {
  item?: AcademicItem;
  courses: Course[];
  defaultCourseId?: string;
  trigger: (open: () => void) => ReactNode;
}) {
  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<ItemForm>(() =>
    formFromItem(item, defaultCourseId),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useDialog(open, dialogRef);

  function openDialog() {
    setForm(formFromItem(item, defaultCourseId));
    setError(null);
    setBusy(false);
    setOpen(true);
  }

  function close() {
    if (busy) return;
    setOpen(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = form.title.trim();
    if (!title) {
      setError("Enter an item title.");
      return;
    }

    let weight: number | null = null;
    if (form.weight.trim()) {
      const parsed = Number(form.weight);
      if (!Number.isFinite(parsed) || parsed < 0 || parsed > 100) {
        setError("Grade weight must be between 0 and 100.");
        return;
      }
      weight = parsed;
    }

    const details = form.details.trim();
    const penalty = form.penalty.trim();
    const startsAt = localInputToIso(form.startsAt);
    const dueAt = localInputToIso(form.dueAt);

    const body: Record<string, unknown> = {
      item_type: form.itemType,
      title,
    };

    if (item) {
      if (details) body.details = details;
      else body.clear_details = true;
      if (form.courseId) body.course_id = form.courseId;
      else body.clear_course = true;
      if (startsAt) body.starts_at = startsAt;
      else body.clear_starts_at = true;
      if (dueAt) body.due_at = dueAt;
      else body.clear_due_at = true;
      if (weight !== null) body.grade_weight_percent = weight;
      else body.clear_grade_weight = true;
      if (penalty) body.late_penalty = penalty;
      else body.clear_late_penalty = true;
      body.review_state = form.reviewState;
    } else {
      body.details = details || null;
      body.course_id = form.courseId || null;
      body.starts_at = startsAt;
      body.due_at = dueAt;
      body.grade_weight_percent = weight;
      body.late_penalty = penalty || null;
    }

    setBusy(true);
    setError(null);
    try {
      const endpoint = item
        ? `/api/academic-items/${encodeURIComponent(item.id)}`
        : "/api/academic-items";
      const response = await fetch(endpoint, {
        method: item ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = (await response.json()) as {
        error?: string;
        details?: { message: string }[];
      };
      if (!response.ok) throw new Error(parseError(data));
      setOpen(false);
      router.refresh();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "The item could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {trigger(openDialog)}
      <dialog
        ref={dialogRef}
        className="task-dialog"
        aria-labelledby={titleId}
        onClose={() => setOpen(false)}
        onClick={(event) => {
          if (event.target === dialogRef.current) close();
        }}>
        <div className="task-dialog-head">
          <h2 id={titleId}>{item ? "Edit item" : "New academic item"}</h2>
          <button
            type="button"
            className="task-dialog-close"
            aria-label="Close"
            onClick={close}>
            <CloseIcon />
          </button>
        </div>
        <form className="task-dialog-body" onSubmit={submit}>
          <div className="task-form-row">
            <div className="field">
              <label htmlFor={`${titleId}-type`}>Type</label>
              <select
                id={`${titleId}-type`}
                value={form.itemType}
                disabled={busy}
                onChange={(event) =>
                  setForm({
                    ...form,
                    itemType: event.target.value as AcademicItemType,
                  })
                }>
                {ITEM_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type[0].toUpperCase() + type.slice(1)}
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
                disabled={busy}
                onChange={(event) =>
                  setForm({ ...form, courseId: event.target.value })
                }>
                <option value="">No course</option>
                {courses.map((course) => (
                  <option key={course.id} value={course.id}>
                    {course.code ? `${course.code} · ` : ""}
                    {course.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="field">
            <label htmlFor={`${titleId}-title`}>Title</label>
            <input
              id={`${titleId}-title`}
              type="text"
              value={form.title}
              maxLength={200}
              autoFocus
              disabled={busy}
              placeholder="e.g. Problem set 4"
              onChange={(event) =>
                setForm({ ...form, title: event.target.value })
              }
            />
          </div>

          <div className="field">
            <label htmlFor={`${titleId}-details`}>
              Details <span className="optional">optional</span>
            </label>
            <textarea
              id={`${titleId}-details`}
              value={form.details}
              maxLength={4000}
              rows={3}
              disabled={busy}
              placeholder="Anything the student needs to remember."
              onChange={(event) =>
                setForm({ ...form, details: event.target.value })
              }
            />
          </div>

          <div className="task-form-row">
            <div className="field">
              <label htmlFor={`${titleId}-starts`}>
                Starts <span className="optional">optional</span>
              </label>
              <input
                id={`${titleId}-starts`}
                type="datetime-local"
                value={form.startsAt}
                disabled={busy}
                onChange={(event) =>
                  setForm({ ...form, startsAt: event.target.value })
                }
              />
            </div>
            <div className="field">
              <label htmlFor={`${titleId}-due`}>
                Due <span className="optional">optional</span>
              </label>
              <input
                id={`${titleId}-due`}
                type="datetime-local"
                value={form.dueAt}
                disabled={busy}
                onChange={(event) =>
                  setForm({ ...form, dueAt: event.target.value })
                }
              />
            </div>
          </div>

          <div className="task-form-row">
            <div className="field">
              <label htmlFor={`${titleId}-weight`}>
                Grade weight % <span className="optional">optional</span>
              </label>
              <input
                id={`${titleId}-weight`}
                type="number"
                min={0}
                max={100}
                step={1}
                value={form.weight}
                placeholder="0–100"
                disabled={busy}
                onChange={(event) =>
                  setForm({ ...form, weight: event.target.value })
                }
              />
            </div>
            <div className="field">
              <label htmlFor={`${titleId}-penalty`}>
                Late penalty <span className="optional">optional</span>
              </label>
              <input
                id={`${titleId}-penalty`}
                type="text"
                value={form.penalty}
                maxLength={200}
                placeholder="e.g. −10% per day"
                disabled={busy}
                onChange={(event) =>
                  setForm({ ...form, penalty: event.target.value })
                }
              />
            </div>
          </div>

          {item ? (
            <div className="field">
              <label htmlFor={`${titleId}-review`}>Review state</label>
              <select
                id={`${titleId}-review`}
                value={form.reviewState}
                disabled={busy}
                onChange={(event) =>
                  setForm({
                    ...form,
                    reviewState: event.target.value as ReviewState,
                  })
                }>
                {REVIEW_STATES.map((state) => (
                  <option key={state} value={state}>
                    {state[0].toUpperCase() + state.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          {error ? (
            <p className="message error" role="alert">
              {error}
            </p>
          ) : null}

          <div className="task-dialog-actions">
            <button className="submit-button" type="submit" disabled={busy}>
              {busy ? "Saving…" : item ? "Save changes" : "Add item"}
            </button>
            <button
              type="button"
              className="connect-button"
              disabled={busy}
              onClick={close}>
              Cancel
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

export function ItemCreateButton({
  courseId,
  courses,
  label = "Add item",
}: {
  courseId?: string;
  courses: Course[];
  label?: string;
}) {
  return (
    <ItemDialogButton
      courses={courses}
      defaultCourseId={courseId}
      trigger={(open) => (
        <button
          type="button"
          className="connect-button connect-button-small"
          onClick={open}>
          {label}
        </button>
      )}
    />
  );
}

export function ItemEditButton({
  item,
  courses,
}: {
  item: AcademicItem;
  courses: Course[];
}) {
  return (
    <ItemDialogButton
      item={item}
      courses={courses}
      trigger={(open) => (
        <button
          type="button"
          className="icon-button"
          aria-label={`Edit ${item.title}`}
          title="Edit item"
          onClick={open}>
          <PencilIcon />
        </button>
      )}
    />
  );
}

// ---------------------------------------------------------------- delete --

export function DeleteRecordButton({
  kind,
  id,
  name,
  redirectTo,
}: {
  kind: "course" | "item";
  id: string;
  name: string;
  /** Navigate here after deleting (used by the item detail page). */
  redirectTo?: string;
}) {
  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useDialog(open, dialogRef);

  const endpoint = kind === "course" ? "courses" : "academic-items";
  const noun = kind === "course" ? "course" : "academic item";

  function close() {
    if (busy) return;
    setOpen(false);
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/${endpoint}/${encodeURIComponent(id)}`,
        {
          method: "DELETE",
        },
      );
      const data = (await response.json()) as { error?: string };
      if (!response.ok)
        throw new Error(data.error || `The ${noun} could not be deleted.`);
      setOpen(false);
      if (redirectTo) router.push(redirectTo);
      else router.refresh();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : `The ${noun} could not be deleted.`,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className="icon-button is-danger"
        aria-label={`Delete ${name}`}
        title={`Delete ${noun}`}
        onClick={() => {
          setError(null);
          setOpen(true);
        }}>
        <TrashIcon />
      </button>
      <dialog
        ref={dialogRef}
        className="task-dialog task-dialog-compact"
        aria-labelledby={titleId}
        onClose={() => setOpen(false)}
        onClick={(event) => {
          if (event.target === dialogRef.current) close();
        }}>
        <div className="task-dialog-head">
          <h2 id={titleId}>Delete {noun}?</h2>
          <button
            type="button"
            className="task-dialog-close"
            aria-label="Close"
            onClick={close}>
            <CloseIcon />
          </button>
        </div>
        <div className="task-dialog-body">
          <p className="panel-note">
            “{name}” will be removed. Linked tasks and courses are kept.
          </p>
          {error ? (
            <p className="message error" role="alert">
              {error}
            </p>
          ) : null}
          <div className="task-dialog-actions">
            <button
              type="button"
              className="submit-button is-danger"
              disabled={busy}
              onClick={confirm}>
              {busy ? "Deleting…" : `Delete ${noun}`}
            </button>
            <button
              type="button"
              className="connect-button"
              disabled={busy}
              onClick={close}>
              Cancel
            </button>
          </div>
        </div>
      </dialog>
    </>
  );
}

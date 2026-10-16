/**
 * Shared shapes and loader for the academic-item and course pickers in the
 * task dialogs. The options endpoint aggregates the backend read routes on the
 * server so the browser stays on the frontend origin.
 */

export type AcademicItemOption = {
  id: string;
  title: string;
  item_type: string;
  due_at: string | null;
};

export type CourseOption = {
  id: string;
  code: string | null;
  name: string;
  term: string | null;
};

export type TaskOptions = {
  academic_items: AcademicItemOption[];
  courses: CourseOption[];
};

/** Load the linkable academic items and courses; throws with the server's message on failure. */
export async function loadTaskOptions(): Promise<TaskOptions> {
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
  return {
    academic_items: data.academic_items ?? [],
    courses: data.courses ?? [],
  };
}

const BACKEND_URL = (process.env.MANUAL_SOURCE_API_URL || "http://127.0.0.1:8001").replace(/\/$/, "");

export type Course = {
  id: string;
  code: string | null;
  name: string;
  term: string | null;
  item_count: number;
  created_at: string;
};

export type CoursePage = {
  items: Course[];
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
};

export type CourseItemSummary = {
  id: string;
  title: string;
  item_type: string;
  review_state: string;
  due_at: string | null;
  grade_weight_percent: string | null;
};

export type CourseDetail = {
  id: string;
  code: string | null;
  name: string;
  term: string | null;
  created_at: string;
  academic_items: CourseItemSummary[];
};

export type AcademicItemType = "assignment" | "announcement" | "reading" | "event";
export type ReviewState = "verified" | "uncertain" | "conflicting";

export type AcademicItem = {
  id: string;
  item_type: AcademicItemType;
  title: string;
  details: string | null;
  course_id: string | null;
  source_revision_id: string | null;
  starts_at: string | null;
  due_at: string | null;
  grade_weight_percent: string | null;
  late_penalty: string | null;
  review_state: ReviewState;
  created_at: string;
  updated_at: string;
};

export type AcademicItemCourse = {
  id: string;
  code: string | null;
  name: string;
  term: string | null;
};

export type AcademicItemDetail = AcademicItem & {
  course: AcademicItemCourse | null;
};

export type AcademicItemPage = {
  items: AcademicItem[];
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
};

export type AcademicItemEvidence = {
  source_document_id: string;
  source_revision_id: string;
  source_title: string | null;
  source_type: string;
  evidence: Record<string, string | null>;
  review_reasons: string[];
  date_facts: Record<string, Record<string, string | null>>;
  original_ref: string | null;
  source_updated_at: string | null;
  observed_at: string | null;
};

export type Change = {
  id: string;
  academic_item_id: string;
  source_revision_id: string | null;
  origin: string;
  change_kind: "created" | "edited";
  before_values: Record<string, unknown> | null;
  after_values: Record<string, unknown>;
  recorded_at: string;
  title: string | null;
  item_type: string | null;
};

export type ChangePage = {
  items: Change[];
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
};

export type AcademicServiceError = Error & { status?: number };

export type CourseCreateInput = {
  name: string;
  code?: string | null;
  term?: string | null;
};

export type CourseUpdateInput = {
  name?: string;
  code?: string | null;
  clear_code?: boolean;
  term?: string | null;
  clear_term?: boolean;
};

export type AcademicItemCreateInput = {
  item_type: AcademicItemType;
  title: string;
  details?: string | null;
  course_id?: string | null;
  starts_at?: string | null;
  due_at?: string | null;
  grade_weight_percent?: number | null;
  late_penalty?: string | null;
};

export type AcademicItemUpdateInput = {
  item_type?: AcademicItemType;
  title?: string;
  details?: string | null;
  clear_details?: boolean;
  course_id?: string | null;
  clear_course?: boolean;
  starts_at?: string | null;
  clear_starts_at?: boolean;
  due_at?: string | null;
  clear_due_at?: boolean;
  grade_weight_percent?: number | null;
  clear_grade_weight?: boolean;
  late_penalty?: string | null;
  clear_late_penalty?: boolean;
  review_state?: ReviewState;
};

function toServiceError(upstream: Response, data: unknown): AcademicServiceError {
  const message =
    typeof data === "object" && data !== null && "error" in data
      ? String((data as { error: unknown }).error)
      : "Could not load academic records.";
  const error = new Error(message) as AcademicServiceError;
  error.status = upstream.status;
  return error;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const upstream = await fetch(`${BACKEND_URL}${path}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(15_000),
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  const payload = await upstream.text();
  let data: T;
  try {
    data = JSON.parse(payload) as T;
  } catch {
    throw new Error("The academic service returned an invalid response.");
  }
  if (!upstream.ok) {
    throw toServiceError(upstream, data);
  }
  return data;
}

function getJson<T>(path: string): Promise<T> {
  return requestJson<T>(path);
}

export function listCourses(search = ""): Promise<CoursePage> {
  return getJson<CoursePage>(`/api/courses${search ? `?${search}` : ""}`);
}

export function getCourse(courseId: string): Promise<CourseDetail> {
  return getJson<CourseDetail>(`/api/courses/${encodeURIComponent(courseId)}`);
}

export function createCourse(input: CourseCreateInput): Promise<Course> {
  return requestJson<Course>("/api/courses", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateCourse(courseId: string, input: CourseUpdateInput): Promise<Course> {
  return requestJson<Course>(`/api/courses/${encodeURIComponent(courseId)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteCourse(courseId: string): Promise<{ id: string; name: string }> {
  return requestJson(`/api/courses/${encodeURIComponent(courseId)}`, { method: "DELETE" });
}

export function listAcademicItems(search = ""): Promise<AcademicItemPage> {
  return getJson<AcademicItemPage>(`/api/academic-items${search ? `?${search}` : ""}`);
}

export function getAcademicItem(itemId: string): Promise<AcademicItemDetail> {
  return getJson<AcademicItemDetail>(`/api/academic-items/${encodeURIComponent(itemId)}`);
}

export function createAcademicItem(input: AcademicItemCreateInput): Promise<AcademicItem> {
  return requestJson<AcademicItem>("/api/academic-items", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateAcademicItem(
  itemId: string,
  input: AcademicItemUpdateInput,
): Promise<AcademicItem> {
  return requestJson<AcademicItem>(`/api/academic-items/${encodeURIComponent(itemId)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteAcademicItem(
  itemId: string,
): Promise<{ id: string; title: string; unlinked_tasks: number; removed_source_links: number }> {
  return requestJson(`/api/academic-items/${encodeURIComponent(itemId)}`, {
    method: "DELETE",
  });
}

/** Source evidence is optional; a manual item has none, so 404 becomes null. */
export async function getAcademicItemEvidence(
  itemId: string,
): Promise<AcademicItemEvidence | null> {
  try {
    return await getJson<AcademicItemEvidence>(
      `/api/academic-items/${encodeURIComponent(itemId)}/evidence`,
    );
  } catch (cause) {
    if ((cause as AcademicServiceError)?.status === 404) return null;
    throw cause;
  }
}

export function listChanges(search = ""): Promise<ChangePage> {
  return getJson<ChangePage>(`/api/changes${search ? `?${search}` : ""}`);
}

export function backendUnavailableMessage(): string {
  return "The academic service is unavailable. Start the backend and try again.";
}

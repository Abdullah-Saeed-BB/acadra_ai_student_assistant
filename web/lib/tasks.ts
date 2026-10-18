const BACKEND_URL = (process.env.MANUAL_SOURCE_API_URL || "http://127.0.0.1:8001").replace(/\/$/, "");

export type Task = {
  id: string;
  title: string;
  details: string | null;
  status: "todo" | "in_progress" | "done";
  selected_day: string | null;
  list_position: number;
  estimated_minutes: number | null;
  tags: string[];
  academic_item_id: string | null;
  course_id: string | null;
  parent_task_id: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TodayPlan = {
  day: string;
  total_estimated_minutes: number;
  tasks: Task[];
};

export type UpcomingDay = {
  day: string;
  total_estimated_minutes: number;
  tasks: Task[];
};

export type UpcomingPlan = {
  start_day: string;
  end_day: string;
  days: UpcomingDay[];
};

export type Backlog = {
  tasks: Task[];
  total_estimated_minutes: number;
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
};

export type TaskPage = {
  items: Task[];
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
};

export type TaskDetail = Task & {
  steps: Task[];
  progress: {
    total_steps: number;
    completed_steps: number;
    unfinished_steps: number;
  };
  academic_item: {
    id: string;
    title: string;
    item_type: string;
    due_at: string | null;
  } | null;
  course: {
    id: string;
    code: string | null;
    name: string;
  } | null;
};

export type TaskServiceError = Error & { status?: number };

export type TaskCreateInput = {
  title: string;
  details?: string | null;
  selected_day?: string | null;
  estimated_minutes?: number | null;
  tags?: string[];
  academic_item_id?: string | null;
  course_id?: string | null;
  parent_task_id?: string | null;
};

export type TaskUpdateInput = {
  title?: string;
  details?: string | null;
  status?: "todo" | "in_progress" | "done";
  selected_day?: string | null;
  clear_selected_day?: boolean;
  list_position?: number;
  estimated_minutes?: number | null;
  tags?: string[];
  parent_task_id?: string | null;
  academic_item_id?: string | null;
  clear_academic_item?: boolean;
  course_id?: string | null;
  clear_course?: boolean;
};

export type TaskDeleteResult = {
  id: string;
  title: string;
  deleted_steps: number;
  academic_item_id: string | null;
  course_id: string | null;
};

function toServiceError(upstream: Response, data: unknown): TaskServiceError {
  const message =
    typeof data === "object" && data !== null && "error" in data
      ? String((data as { error: unknown }).error)
      : "Could not load tasks.";
  const error = new Error(message) as TaskServiceError;
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
    throw new Error("The task service returned an invalid response.");
  }
  if (!upstream.ok) {
    throw toServiceError(upstream, data);
  }
  return data;
}

async function getJson<T>(path: string): Promise<T> {
  return requestJson<T>(path);
}

export function getTodayPlan(timezone?: string): Promise<TodayPlan> {
  const query = timezone ? `?timezone=${encodeURIComponent(timezone)}` : "";
  return getJson<TodayPlan>(`/api/plan/today${query}`);
}

export function getUpcomingPlan(days = 7): Promise<UpcomingPlan> {
  return getJson<UpcomingPlan>(`/api/plan/upcoming?days=${days}`);
}

export function getBacklog(limit = 50): Promise<Backlog> {
  return getJson<Backlog>(`/api/plan/backlog?limit=${limit}`);
}

export function listTasks(search: string): Promise<TaskPage> {
  return getJson<TaskPage>(`/api/tasks${search ? `?${search}` : ""}`);
}

export function getTask(taskId: string): Promise<TaskDetail> {
  return getJson<TaskDetail>(`/api/tasks/${encodeURIComponent(taskId)}`);
}

export function createTask(input: TaskCreateInput): Promise<Task> {
  return requestJson<Task>("/api/tasks", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateTask(
  taskId: string,
  input: TaskUpdateInput,
): Promise<Task> {
  return requestJson<Task>(`/api/tasks/${encodeURIComponent(taskId)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteTask(taskId: string): Promise<TaskDeleteResult> {
  return requestJson<TaskDeleteResult>(
    `/api/tasks/${encodeURIComponent(taskId)}`,
    { method: "DELETE" },
  );
}

export function backendUnavailableMessage(): string {
  return "The task service is unavailable. Start the backend and try again.";
}

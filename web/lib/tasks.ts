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

async function getJson<T>(path: string): Promise<T> {
  const upstream = await fetch(`${BACKEND_URL}${path}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(15_000),
  });
  const payload = await upstream.text();
  let data: T;
  try {
    data = JSON.parse(payload) as T;
  } catch {
    throw new Error("The task service returned an invalid response.");
  }
  if (!upstream.ok) {
    const message =
      typeof data === "object" && data !== null && "error" in data
        ? String((data as { error: unknown }).error)
        : "Could not load tasks.";
    const error = new Error(message) as TaskServiceError;
    error.status = upstream.status;
    throw error;
  }
  return data;
}

export function getTodayPlan(): Promise<TodayPlan> {
  return getJson<TodayPlan>("/api/plan/today");
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

export function backendUnavailableMessage(): string {
  return "The task service is unavailable. Start the backend and try again.";
}

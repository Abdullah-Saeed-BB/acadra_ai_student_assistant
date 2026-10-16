import { proxyJsonRequest } from "@/lib/proxy";

/**
 * Proxies single-task reads, partial task updates (status, title, details,
 * day, effort, tags), and deletions to the backend REST boundary. The browser
 * never reaches the Python listener directly; this route stays on the
 * frontend origin and keeps the backend URL server-side, like the other
 * proxy routes.
 *
 * The GET is what the delete confirm uses to list a task's steps before the
 * DELETE runs, so the warning can name everything the deletion takes.
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ task_id: string }> },
) {
  const { task_id } = await params;
  return proxyJsonRequest(
    request,
    `/api/tasks/${encodeURIComponent(task_id)}`,
    "task service",
  );
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ task_id: string }> },
) {
  const { task_id } = await params;
  return proxyJsonRequest(
    request,
    `/api/tasks/${encodeURIComponent(task_id)}`,
    "task service",
  );
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ task_id: string }> },
) {
  const { task_id } = await params;
  return proxyJsonRequest(
    request,
    `/api/tasks/${encodeURIComponent(task_id)}`,
    "task service",
  );
}

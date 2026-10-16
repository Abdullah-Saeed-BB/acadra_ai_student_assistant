import { proxyJsonRequest } from "@/lib/proxy";

/** Proxies course edits and deletions to the backend REST boundary. */
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ course_id: string }> },
) {
  const { course_id } = await params;
  return proxyJsonRequest(
    request,
    `/api/courses/${encodeURIComponent(course_id)}`,
    "course service",
  );
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ course_id: string }> },
) {
  const { course_id } = await params;
  return proxyJsonRequest(
    request,
    `/api/courses/${encodeURIComponent(course_id)}`,
    "course service",
  );
}

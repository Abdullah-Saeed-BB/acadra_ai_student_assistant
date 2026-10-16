const DEFAULT_BACKEND_URL = "http://127.0.0.1:8001";

/**
 * Options for the create-task dialog: the academic items and courses a task can
 * be linked to. This aggregates the backend read routes on the server so the
 * browser stays on the frontend origin.
 */
export async function GET() {
  const backendUrl = (process.env.MANUAL_SOURCE_API_URL || DEFAULT_BACKEND_URL).replace(/\/$/, "");
  try {
    const [itemsResponse, coursesResponse] = await Promise.all([
      fetch(`${backendUrl}/api/academic-items?limit=100`, {
        cache: "no-store",
        signal: AbortSignal.timeout(15_000),
      }),
      fetch(`${backendUrl}/api/courses?limit=100`, {
        cache: "no-store",
        signal: AbortSignal.timeout(15_000),
      }),
    ]);
    if (!itemsResponse.ok || !coursesResponse.ok) {
      return Response.json(
        { error: "The academic items and courses could not be loaded." },
        { status: 502 },
      );
    }
    const items = (await itemsResponse.json()) as { items?: unknown[] };
    const courses = (await coursesResponse.json()) as { items?: unknown[] };
    return Response.json({
      academic_items: items.items ?? [],
      courses: courses.items ?? [],
    });
  } catch {
    return Response.json(
      { error: "The task service is unavailable. Start the backend and try again." },
      { status: 503 },
    );
  }
}

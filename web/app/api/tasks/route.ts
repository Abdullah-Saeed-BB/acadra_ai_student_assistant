import { proxyJsonRequest } from "@/lib/proxy";

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8001";
const MAX_BODY_BYTES = 64 * 1024;

/**
 * Creates a task through the backend REST boundary. The browser never reaches
 * the Python listener directly; this route stays on the frontend origin and
 * keeps the backend URL server-side, like the other proxy routes.
 */
export async function POST(request: Request) {
  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.startsWith("application/json")) {
    return Response.json(
      { error: "Content-Type must be application/json." },
      { status: 415 },
    );
  }

  const body = await request.arrayBuffer();
  if (body.byteLength > MAX_BODY_BYTES) {
    return Response.json({ error: "Request body is too large." }, { status: 413 });
  }

  const backendUrl = (process.env.MANUAL_SOURCE_API_URL || DEFAULT_BACKEND_URL).replace(/\/$/, "");
  try {
    const upstream = await fetch(`${backendUrl}/api/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
    });
    const payload = await upstream.text();
    try {
      return Response.json(JSON.parse(payload), { status: upstream.status });
    } catch {
      return Response.json(
        { error: "The task service returned an invalid response." },
        { status: 502 },
      );
    }
  } catch {
    return Response.json(
      { error: "The task service is unavailable. Start the backend and try again." },
      { status: 503 },
    );
  }
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  return proxyJsonRequest(request, `/api/tasks${url.search}`, "task service");
}

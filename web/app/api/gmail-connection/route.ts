const BACKEND_URL = (process.env.MANUAL_SOURCE_API_URL || "http://127.0.0.1:8001").replace(/\/$/, "");

async function forward(method: "GET" | "PUT", body?: string) {
  try {
    const upstream = await fetch(`${BACKEND_URL}/api/connections/gmail`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    const payload = await upstream.json();
    return Response.json(payload, {
      status: upstream.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json(
      { error: "The Gmail setup service is unavailable. Start the backend and try again." },
      { status: 503 },
    );
  }
}

export async function GET() {
  return forward("GET");
}

export async function PUT(request: Request) {
  const origin = request.headers.get("origin");
  if (origin && origin !== new URL(request.url).origin) {
    return Response.json({ error: "Invalid request origin." }, { status: 403 });
  }
  if (!request.headers.get("content-type")?.startsWith("application/json")) {
    return Response.json({ error: "Content-Type must be application/json." }, { status: 415 });
  }
  const body = await request.text();
  if (new TextEncoder().encode(body).length > 16 * 1024) {
    return Response.json({ error: "Configuration is too large." }, { status: 413 });
  }
  return forward("PUT", body);
}

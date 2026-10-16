const DEFAULT_BACKEND_URL = "http://127.0.0.1:8001";
const MAX_BODY_BYTES = 64 * 1024;

/**
 * Forward a browser mutation to the Python REST boundary from the frontend
 * origin. The backend URL stays server-side, matching the task proxy routes.
 *
 * GET and DELETE are treated as body-less; JSON payload methods must send a
 * JSON Content-Type under the body-size cap.
 */
export async function proxyJsonRequest(
  request: Request,
  backendPath: string,
  errorLabel = "academic service",
): Promise<Response> {
  const hasBody = request.method !== "GET" && request.method !== "DELETE";

  let body: ArrayBuffer | undefined;
  if (hasBody) {
    const contentType = request.headers.get("content-type") ?? "";
    if (!contentType.startsWith("application/json")) {
      return Response.json(
        { error: "Content-Type must be application/json." },
        { status: 415 },
      );
    }
    body = await request.arrayBuffer();
    if (body.byteLength > MAX_BODY_BYTES) {
      return Response.json({ error: "Request body is too large." }, { status: 413 });
    }
  }

  const backendUrl = (process.env.MANUAL_SOURCE_API_URL || DEFAULT_BACKEND_URL).replace(/\/$/, "");
  try {
    const upstream = await fetch(`${backendUrl}${backendPath}`, {
      method: request.method,
      headers: hasBody ? { "Content-Type": "application/json" } : undefined,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
    });
    const payload = await upstream.text();
    try {
      return Response.json(JSON.parse(payload), { status: upstream.status });
    } catch {
      return Response.json(
        { error: `The ${errorLabel} returned an invalid response.` },
        { status: 502 },
      );
    }
  } catch {
    return Response.json(
      { error: `The ${errorLabel} is unavailable. Start the backend and try again.` },
      { status: 503 },
    );
  }
}

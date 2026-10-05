const DEFAULT_BACKEND_URL = "http://127.0.0.1:8001";
const MAX_BODY_BYTES = 5 * 1024 * 1024 + 16 * 1024;

export async function POST(request: Request) {
  const contentType = request.headers.get("content-type") ?? "";
  const isText = contentType.startsWith("application/json");
  const isFile = contentType.startsWith("multipart/form-data;");
  if (!isText && !isFile) {
    return Response.json({ error: "Submit text or an HTML/PDF file." }, { status: 415 });
  }

  const length = Number(request.headers.get("content-length"));
  if (Number.isFinite(length) && length > MAX_BODY_BYTES) {
    return Response.json({ error: "Upload is too large." }, { status: 413 });
  }

  const body = await request.arrayBuffer();
  if (body.byteLength > MAX_BODY_BYTES) {
    return Response.json({ error: "Upload is too large." }, { status: 413 });
  }

  const backendUrl = (process.env.MANUAL_SOURCE_API_URL || DEFAULT_BACKEND_URL).replace(/\/$/, "");
  try {
    const upstream = await fetch(`${backendUrl}/api/sources/${isText ? "text" : "files"}`, {
      method: "POST",
      headers: { "Content-Type": contentType },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(90_000),
    });
    const payload = await upstream.text();
    try {
      return Response.json(JSON.parse(payload), { status: upstream.status });
    } catch {
      return Response.json({ error: "The source service returned an invalid response." }, { status: 502 });
    }
  } catch {
    return Response.json({ error: "The source service is unavailable. Start the backend and try again." }, { status: 503 });
  }
}

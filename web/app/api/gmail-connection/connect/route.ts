const BACKEND_URL = (process.env.MANUAL_SOURCE_API_URL || "http://127.0.0.1:8001").replace(/\/$/, "");

export async function GET() {
  return Response.redirect(`${BACKEND_URL}/api/connections/gmail/authorize`, 303);
}

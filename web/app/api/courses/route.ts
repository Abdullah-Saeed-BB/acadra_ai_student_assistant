import { proxyJsonRequest } from "@/lib/proxy";

/**
 * Creates a course through the backend REST boundary. The browser never
 * reaches the Python listener directly.
 */
export async function POST(request: Request) {
  return proxyJsonRequest(request, "/api/courses", "course service");
}

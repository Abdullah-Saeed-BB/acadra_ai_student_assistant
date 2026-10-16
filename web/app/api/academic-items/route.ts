import { proxyJsonRequest } from "@/lib/proxy";

/**
 * Creates a manually recorded academic item through the backend REST boundary.
 * The browser never reaches the Python listener directly.
 */
export async function POST(request: Request) {
  return proxyJsonRequest(request, "/api/academic-items", "academic item service");
}

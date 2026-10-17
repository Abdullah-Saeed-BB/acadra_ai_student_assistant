import { proxyJsonRequest } from "@/lib/proxy";

export async function GET(request: Request) {
  return proxyJsonRequest(request, "/api/preferences", "preferences service");
}

export async function PUT(request: Request) {
  return proxyJsonRequest(request, "/api/preferences", "preferences service");
}
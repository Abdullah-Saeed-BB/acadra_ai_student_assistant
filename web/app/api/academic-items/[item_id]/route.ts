import { proxyJsonRequest } from "@/lib/proxy";

/** Proxies academic item edits and deletions to the backend REST boundary. */
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ item_id: string }> },
) {
  const { item_id } = await params;
  return proxyJsonRequest(
    request,
    `/api/academic-items/${encodeURIComponent(item_id)}`,
    "academic item service",
  );
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ item_id: string }> },
) {
  const { item_id } = await params;
  return proxyJsonRequest(
    request,
    `/api/academic-items/${encodeURIComponent(item_id)}`,
    "academic item service",
  );
}

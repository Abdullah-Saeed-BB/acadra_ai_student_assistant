/**
 * Alexa+ chat bridge (placeholder).
 *
 * This route is the single seam where the simulator will hand a conversation to
 * the Python MCP server. The browser posts `{ messages: [{ role, text }] }` and
 * expects `{ reply: string }` back. Until the MCP transport is wired up the
 * route reports 501 and the client falls back to its scripted replies.
 *
 * TODO(MCP): forward `messages` to the backend's Streamable HTTP MCP endpoint
 * (see `app/mcp_server/`) using a server-side client, then return the answer as
 * `{ reply }`. Keep the MCP credentials on this server; never send them to the
 * browser.
 */
export async function POST() {
  return Response.json(
    { error: "The Alexa+ MCP bridge is not connected yet." },
    { status: 501 },
  );
}

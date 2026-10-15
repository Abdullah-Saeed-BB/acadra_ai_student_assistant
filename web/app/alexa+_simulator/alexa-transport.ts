export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
};

/**
 * The MCP bridge endpoint. The Next.js route handler at
 * `app/api/alexa-chat/route.ts` forwards a conversation to the Python MCP server
 * through `lib/mcp-client.ts`; the browser never talks to the MCP server
 * directly.
 */
export const ALEXA_BRIDGE_ENDPOINT = "/api/alexa-chat";

/**
 * When the bridge answers with a non-2xx status, an empty reply, or a network
 * error, the simulator shows this instead of a scripted domain answer.
 */
const FALLBACK_ERROR_REPLY =
  "Sorry, something dropped on my end. Please try again in a moment.";

/**
 * Turns the conversation so far into Alexa+'s next reply.
 *
 * Every message goes to the LLM through the MCP bridge, which decides which
 * `study_*` tool to call. There are no scripted fallbacks: any bridge failure
 * returns a short apology so the send, thinking, and reply states still work
 * end to end.
 */
export async function requestAlexaReply(messages: ChatMessage[]): Promise<string> {
  const bridgeReply = await requestFromBridge(messages);
  return bridgeReply ?? FALLBACK_ERROR_REPLY;
}

/**
 * Posts the conversation to the bridge and returns its reply, or null when the
 * bridge is unavailable so the caller can answer with the fallback message.
 */
async function requestFromBridge(messages: ChatMessage[]): Promise<string | null> {
  try {
    const response = await fetch(ALEXA_BRIDGE_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: messages.map(({ role, text }) => ({ role, text })),
      }),
      cache: "no-store",
    });
    if (!response.ok) return null;
    const data: { reply?: string } = await response.json();
    return typeof data.reply === "string" && data.reply.trim() ? data.reply : null;
  } catch {
    return null;
  }
}

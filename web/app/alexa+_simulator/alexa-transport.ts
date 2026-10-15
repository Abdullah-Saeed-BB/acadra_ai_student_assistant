import type { AgentTrace } from "@/lib/mcp-client";

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
  "Sorry, error occurs. Please try again in a moment.";

/** Where a frontend-side failure happened (browser fetch / bridge HTTP). */
export type FrontendErrorTrace = {
  source: "frontend" | "bridge-http";
  message: string;
  detail?: string;
  status?: number;
  rawBody?: string;
};

export type BridgeResult = {
  reply: string;
  /** Server-side agent trace (thoughts, tool calls, outputs). Null when the bridge never produced one. */
  trace: AgentTrace | null;
  /** Set when the reply is the fallback: network error, non-2xx, or bad JSON. */
  frontendError?: FrontendErrorTrace | null;
};

/**
 * Turns the conversation so far into Alexa+'s next reply.
 *
 * Every message goes to the LLM through the MCP bridge, which decides which
 * `study_*` tool to call. There are no scripted fallbacks: any bridge failure
 * returns a short apology so the send, thinking, and reply states still work
 * end to end.
 */
export async function requestAlexaReply(
  messages: ChatMessage[],
): Promise<string> {
  const result = await requestAlexaWithTrace(messages);
  return result.reply;
}

/**
 * TEMP-DEBUG: same bridge call, but keeps the agent trace and the full
 * frontend/bridge error log so `components/temp-agent-trace.tsx` can render it.
 */
export async function requestAlexaWithTrace(
  messages: ChatMessage[],
): Promise<BridgeResult> {
  const startedAt = Date.now();
  let response: Response;
  try {
    response = await fetch(ALEXA_BRIDGE_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: messages.map(({ role, text }) => ({ role, text })),
      }),
      cache: "no-store",
    });
  } catch (error) {
    // Browser network failure: the request never reached the bridge.
    return {
      reply: FALLBACK_ERROR_REPLY,
      trace: null,
      frontendError: {
        source: "frontend",
        message:
          "Browser fetch to /api/alexa-chat threw before getting a response.",
        detail: `${error instanceof Error ? `${error.name}: ${error.message}` : String(error)} (after ${Date.now() - startedAt}ms)`,
      },
    };
  }

  let data: { reply?: unknown; trace?: unknown; error?: unknown } = {};
  let rawBody = "";
  try {
    rawBody = await response.text();
    data = rawBody ? (JSON.parse(rawBody) as typeof data) : {};
  } catch (error) {
    return {
      reply: FALLBACK_ERROR_REPLY,
      trace: null,
      frontendError: {
        source: "frontend",
        message: `Bridge answered HTTP ${response.status} with a body that is not valid JSON.`,
        detail: `${error instanceof Error ? `${error.name}: ${error.message}` : String(error)} | rawBody: ${rawBody.slice(0, 2000)}`,
        status: response.status,
        rawBody: rawBody.slice(0, 4000),
      },
    };
  }

  const trace = (data.trace ?? null) as AgentTrace | null;

  if (!response.ok) {
    // Bridge down (503/500/4xx): server already attached a partial trace when it had one.
    const serverMessage =
      typeof data.error === "string"
        ? data.error
        : "Bridge answered with a non-2xx status.";
    return {
      reply: FALLBACK_ERROR_REPLY,
      trace,
      frontendError: {
        source: "bridge-http",
        message: serverMessage,
        detail: `HTTP ${response.status} ${response.statusText} after ${Date.now() - startedAt}ms. Raw body: ${rawBody.slice(0, 2000)}`,
        status: response.status,
        rawBody: rawBody.slice(0, 4000),
      },
    };
  }

  const reply =
    typeof data.reply === "string" && data.reply.trim() ? data.reply : null;
  if (!reply) {
    return {
      reply: FALLBACK_ERROR_REPLY,
      trace,
      frontendError: {
        source: "bridge-http",
        message: "Bridge answered 200 but the reply was empty or missing.",
        detail: `Raw body: ${rawBody.slice(0, 2000)}`,
        status: response.status,
        rawBody: rawBody.slice(0, 4000),
      },
    };
  }
  return { reply, trace, frontendError: null };
}

/**
 * Posts the conversation to the bridge and returns its reply, or null when the
 * bridge is unavailable so the caller can answer with the fallback message.
 */
async function requestFromBridge(
  messages: ChatMessage[],
): Promise<string | null> {
  const result = await requestAlexaWithTrace(messages);
  return result.frontendError ? null : result.reply;
}

/**
 * Alexa+ chat bridge.
 *
 * The simulator posts `{ messages: [{ role, text }] }` here; this route validates
 * the conversation, forwards it to the Python study planner over MCP through the
 * server-side client in `lib/mcp-client.ts`, and returns `{ reply }`. MCP
 * credentials and the endpoint URL stay on the server and never reach the
 * browser.
 *
 * A 2xx response carries a reply (including tool-level errors rendered as text).
 * A 503 means the bridge itself is down (MCP unreachable, chat model missing or
 * failed), which lets `alexa-transport.ts` answer with its fallback message.
 */

import { z } from "zod";

import { McpUnavailableError, replyWithTrace } from "@/lib/mcp-client";

export const runtime = "nodejs";

const MAX_BODY_BYTES = 64 * 1024;

const ChatMessageSchema = z.strictObject({
  role: z.enum(["user", "assistant"]),
  text: z.string().trim().min(1).max(4000),
});

const AlexaChatRequestSchema = z.strictObject({
  messages: z.array(ChatMessageSchema).min(1).max(50),
});

export async function POST(request: Request) {
  const origin = request.headers.get("origin");
  if (origin && origin !== new URL(request.url).origin) {
    return Response.json({ error: "Invalid request origin." }, { status: 403 });
  }
  if (!request.headers.get("content-type")?.startsWith("application/json")) {
    return Response.json({ error: "Content-Type must be application/json." }, { status: 415 });
  }

  const body = await request.text();
  if (new TextEncoder().encode(body).length > MAX_BODY_BYTES) {
    return Response.json({ error: "The conversation is too large." }, { status: 413 });
  }

  let payload: unknown;
  try {
    payload = JSON.parse(body);
  } catch {
    return Response.json({ error: "The request body is not valid JSON." }, { status: 400 });
  }

  const parsed = AlexaChatRequestSchema.safeParse(payload);
  if (!parsed.success) {
    return Response.json({ error: "Send { messages: [{ role, text }] }." }, { status: 400 });
  }

  try {
    const { reply, trace } = await replyWithTrace(parsed.data.messages);
    return Response.json({ reply, trace }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    if (error instanceof McpUnavailableError) {
      // Non-200 so the simulator can answer with its fallback message.
      // TEMP-DEBUG: still include the partial agent trace when we have one.
      return Response.json(
        { error: "The Alexa+ MCP bridge is unavailable.", trace: error.agentTrace ?? null },
        { status: 503, headers: { "Cache-Control": "no-store" } },
      );
    }
    console.error("alexa-chat bridge error:", error);
    return Response.json(
      { error: "The Alexa+ bridge could not complete the request.", trace: null },
      { status: 500, headers: { "Cache-Control": "no-store" } },
    );
  }
}

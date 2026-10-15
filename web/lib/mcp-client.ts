/**
 * Server-side MCP client for the Alexa+ bridge.
 *
 * This is the single place where the Next.js app talks to the Python study
 * planner MCP server over its Streamable HTTP endpoint (`/mcp`). The browser
 * never reaches this code: `app/api/alexa-chat/route.ts` calls
 * `replyToConversation`, which opens a client, discovers the `study_*` tools,
 * lets the configured chat model call them, and turns the result into a reply
 * string. MCP credentials and the
 * endpoint URL stay on the server.
 *
 * The client connects with the `@modelcontextprotocol/sdk`, so the session and
 * streaming behaviour are negotiated automatically and match whatever transport
 * mode the backend serves. The backend currently runs `streamable_http_app()`
 * with its defaults (stateful sessions, SSE responses); the SDK handles the
 * `Mcp-Session-Id` header and the SSE stream for us. If the backend is later
 * switched to stateless JSON, this client keeps working because the transport
 * mode is negotiated, not hard-coded.
 *
 * Lifecycle: a client and transport are created per request and always closed in
 * `finally`. Sessions are explicitly terminated so stateful backends do not
 * accumulate idle sessions.
 */

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const DEFAULT_MCP_SERVER_URL = "http://127.0.0.1:8001/mcp";

/**
 * Wall-clock budget for one request/response round trip (connect, discovery, or
 * a tool call). Long-lived GET streams used for server push are not time-boxed.
 */
const REQUEST_TIMEOUT_MS = 15_000;

const BRIDGE_CLIENT_NAME = "acadra-web-bridge";
const BRIDGE_CLIENT_VERSION = "0.1.0";

export const MCP_SERVER_URL = (process.env.MCP_SERVER_URL?.trim() || DEFAULT_MCP_SERVER_URL).replace(/\/+$/, "");

export type ChatRole = "user" | "assistant";

export type StudyChatMessage = {
  role: ChatRole;
  text: string;
};

/** A discovered `study_*` tool, as reported by `tools/list`. */
export type StudyToolSummary = {
  name: string;
  description: string;
  readOnly: boolean;
};

/** The shared error envelope the study planner tools return in their payload. */
export type StudyToolError = {
  code: string;
  message: string;
  hint?: string;
};

export type StudyToolOutcome =
  | { tool: string; ok: true; data: Record<string, unknown>; text: string | null }
  | { tool: string; ok: false; error: StudyToolError };

/**
 * Raised when the MCP endpoint cannot be reached, no chat model is configured,
 * or the model request fails. The route maps this to a non-200 response so
 * `alexa-transport.ts` can answer with its fallback message. Tool-level
 * failures are *not* thrown: they come back as
 * `{ ok: false }` outcomes and are rendered as an actionable reply.
 */
export class McpUnavailableError extends Error {
  /** Partial agent trace collected before the failure, so the bridge can still return it. */
  agentTrace?: AgentTrace | null;
  constructor(message = "The study planner MCP server is unavailable.", trace?: AgentTrace | null) {
    super(message);
    this.name = "McpUnavailableError";
    this.agentTrace = trace ?? null;
  }
}

/**
 * TEMP-DEBUG trace model for the AI agent process.
 * Collected server-side in `replyWithTrace` and rendered by
 * `components/temp-agent-trace.tsx`. Keep JSON-serializable (no Error objects).
 */
export type AgentToolCallTrace = {
  id: string;
  name: string;
  argumentsRaw: string;
  argumentsParsed: Record<string, unknown>;
};

export type AgentToolOutputTrace = {
  tool: string;
  ok: boolean;
  /** Text fed back to the LLM (rendered outcome or failure string). */
  renderedText: string;
  /** Raw normalized outcome data when available. */
  data?: Record<string, unknown>;
  error?: StudyToolError;
};

export type AgentStepTrace = {
  round: number;
  /** Raw LLM message content for this round: pre-tool thought / draft answer. */
  llmThought: string | null;
  toolCalls: AgentToolCallTrace[];
  toolOutputs: AgentToolOutputTrace[];
  /** LLM request failure for this round, if any. */
  llmError?: string;
};

export type AgentErrorTrace = {
  /** Where the failure surfaced: bridge validation, MCP transport, or the chat model. */
  source: "bridge" | "mcp" | "llm";
  message: string;
  detail?: string;
};

export type AgentTrace = {
  model: string;
  mcpServerUrl: string;
  toolsDiscovered: string[];
  steps: AgentStepTrace[];
  finalReply: string | null;
  error?: AgentErrorTrace;
};

type McpToolResult = Awaited<ReturnType<Client["callTool"]>>;

/**
 * Wraps global `fetch` so request/response calls cannot hang. GET requests are
 * left alone because they carry the long-lived SSE stream; POST and DELETE calls
 * get a combined signal that still honours the transport's own abort.
 */
function createFetch(): (url: string | URL, init?: RequestInit) => Promise<Response> {
  return (url, init) => {
    const method = (init?.method ?? "GET").toUpperCase();
    if (method === "GET") {
      return fetch(url, init);
    }
    const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
    const signal = init?.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
    return fetch(url, { ...init, signal });
  };
}

async function closeClient(client: Client, transport: StreamableHTTPClientTransport): Promise<void> {
  // Terminate the session first (best effort; a stateless server answers 405),
  // then drop the transport and its open SSE stream.
  try {
    await transport.terminateSession();
  } catch {
    // Ignore: the session may already be gone or termination may be unsupported.
  }
  try {
    await client.close();
  } catch {
    // Ignore: closing is best effort.
  }
}

/**
 * Opens one client/transport pair for the lifetime of `run`, then always closes
 * it. Infrastructure failures are normalised to `McpUnavailableError`.
 */
async function withStudyClient<T>(run: (client: Client) => Promise<T>): Promise<T> {
  const transport = new StreamableHTTPClientTransport(new URL(MCP_SERVER_URL), {
    fetch: createFetch(),
    requestInit: { cache: "no-store" },
  });
  const client = new Client(
    { name: BRIDGE_CLIENT_NAME, version: BRIDGE_CLIENT_VERSION },
    { capabilities: {} },
  );

  try {
    await client.connect(transport);
  } catch (error) {
    await closeClient(client, transport);
    throw new McpUnavailableError(
      `Could not connect to the study planner MCP server at ${MCP_SERVER_URL}: ${describeError(error)}`,
    );
  }

  try {
    return await run(client);
  } catch (error) {
    if (error instanceof McpUnavailableError) throw error;
    throw new McpUnavailableError(`The study planner MCP request failed: ${describeError(error)}`);
  } finally {
    await closeClient(client, transport);
  }
}

/**
 * Lists the `study_*` tools the server advertises. Useful for discovery and for
 * checking that a tool exists before calling it.
 */
export async function listStudyTools(): Promise<StudyToolSummary[]> {
  return withStudyClient(async (client) => {
    const { tools } = await client.listTools();
    return tools
      .filter((tool) => tool.name.startsWith("study_"))
      .map((tool) => ({
        name: tool.name,
        description: tool.description ?? "",
        readOnly: tool.annotations?.readOnlyHint === true,
      }));
  });
}

/** Calls one `study_*` tool and normalises the result. */
export async function callStudyTool(
  name: string,
  args: Record<string, unknown>,
): Promise<StudyToolOutcome> {
  return withStudyClient(async (client) => {
    const result = await client.callTool({ name, arguments: args });
    return normalizeToolResult(name, result);
  });
}

type ToolCallPayload = {
  content?: Array<{ type: string; text?: string }>;
  structuredContent?: Record<string, unknown>;
  isError?: boolean;
  toolResult?: unknown;
};

function normalizeToolResult(tool: string, result: McpToolResult): StudyToolOutcome {
  const payload = result as ToolCallPayload;

  // Some servers answer with the legacy `toolResult` shape.
  if (payload.toolResult !== undefined && !payload.content) {
    const text = stringifyUnknown(payload.toolResult);
    return { tool, ok: true, data: {}, text };
  }

  const structured = payload.structuredContent ?? null;
  const textBlock = payload.content?.find((block) => block.type === "text");
  const rawText = textBlock?.text ?? null;
  const parsed = structured ?? parseJsonObject(rawText);

  if (payload.isError) {
    return { tool, ok: false, error: extractError(parsed, rawText) };
  }
  return { tool, ok: true, data: parsed ?? {}, text: rawText };
}

function extractError(parsed: Record<string, unknown> | null, rawText: string | null): StudyToolError {
  const envelope = parsed?.error;
  if (envelope && typeof envelope === "object") {
    const error = envelope as Record<string, unknown>;
    if (typeof error.message === "string" && error.message.trim()) {
      return {
        code: typeof error.code === "string" ? error.code : "error",
        message: error.message,
        hint: typeof error.hint === "string" ? error.hint : undefined,
      };
    }
  }
  return {
    code: "error",
    message: rawText?.trim() || "The study planner could not complete that request.",
  };
}

function parseJsonObject(text: string | null): Record<string, unknown> | null {
  if (!text) return null;
  try {
    const value: unknown = JSON.parse(text);
    return value && typeof value === "object" && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function stringifyUnknown(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (value == null) return null;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return null;
  }
}

function describeError(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

/**
 * Answers one simulator conversation with an LLM tool-calling loop.
 *
 * The conversation is sent to the configured chat model together with the
 * `study_*` tools discovered over MCP. The model decides which tool (if any)
 * to call; each call is executed through the MCP client and its rendered
 * result is fed back until the model produces a final answer.
 *
 * Throws `McpUnavailableError` when the MCP endpoint cannot be reached, no chat
 * model is configured, or the model request fails, so the route can report
 * "bridge down" and the simulator can answer with its fallback message.
 */
export async function replyToConversation(messages: StudyChatMessage[]): Promise<string> {
  const { reply } = await replyWithTrace(messages);
  return reply;
}

/**
 * TEMP-DEBUG: same LLM tool-calling loop as before, but also records every
 * round (LLM thought, tool calls, tool outputs) into an `AgentTrace`.
 * On success resolves `{ reply, trace }`. On bridge/MCP/LLM failure it throws
 * `McpUnavailableError` with the partial trace attached as `error.agentTrace`
 * so `app/api/alexa-chat/route.ts` can still return it to the temp viewer.
 */
export async function replyWithTrace(
  messages: StudyChatMessage[],
): Promise<{ reply: string; trace: AgentTrace }> {
  const llm = getLlmConfig();
  const mcpServerUrl = MCP_SERVER_URL;
  if (!llm) {
    const trace: AgentTrace = {
      model: "(unconfigured)",
      mcpServerUrl,
      toolsDiscovered: [],
      steps: [],
      finalReply: null,
      error: {
        source: "llm",
        message: "The chat model is not configured.",
        detail: "Set MODEL_PROVIDER/MODEL_NAME plus its API key (GROQ_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY).",
      },
    };
    throw new McpUnavailableError(
      "The chat model is not configured. Set MODEL_PROVIDER/MODEL_NAME plus its API key.",
      trace,
    );
  }

  return withStudyClient(async (client) => {
    const trace: AgentTrace = {
      model: llm.model,
      mcpServerUrl,
      toolsDiscovered: [],
      steps: [],
      finalReply: null,
    };
    const fail = (message: string, error: AgentErrorTrace): never => {
      trace.error = error;
      throw new McpUnavailableError(message, trace);
    };

    let studyTools: Awaited<ReturnType<Client["listTools"]>>["tools"];
    try {
      ({ tools: studyTools } = await client.listTools());
    } catch (error) {
      return fail(`The study planner MCP request failed: ${describeError(error)}`, {
        source: "mcp",
        message: "tools/list failed.",
        detail: describeError(error),
      });
    }
    const filtered = studyTools.filter((tool) => tool.name.startsWith("study_"));
    trace.toolsDiscovered = filtered.map((tool) => tool.name);
    if (filtered.length === 0) {
      return fail("The study planner exposed no study_* tools.", {
        source: "mcp",
        message: "The study planner exposed no study_* tools.",
        detail: `tools/list returned ${studyTools.length} tool(s), none prefixed study_.`,
      });
    }
    const chatTools = filtered.map((tool) => ({
      type: "function" as const,
      function: {
        name: tool.name,
        description: tool.description ?? "",
        parameters:
          tool.inputSchema && typeof tool.inputSchema === "object"
            ? (tool.inputSchema as Record<string, unknown>)
            : { type: "object", properties: {} },
      },
    }));

    const chatMessages: ChatCompletionMessage[] = [
      { role: "system", content: CHAT_SYSTEM_PROMPT },
      ...messages.map(
        (message): ChatCompletionMessage => ({
          role: message.role,
          content: message.text,
        }),
      ),
    ];

    for (let round = 0; round < MAX_TOOL_ROUNDS; round += 1) {
      const step: AgentStepTrace = { round: round + 1, llmThought: null, toolCalls: [], toolOutputs: [] };
      trace.steps.push(step);

      let answer: { content: string | null; tool_calls?: ChatToolCall[] };
      try {
        answer = await completeChat(llm, chatMessages, chatTools);
      } catch (error) {
        const detail = describeError(error);
        step.llmError = detail;
        return fail(`The chat model request failed: ${detail}`, {
          source: "llm",
          message: `Round ${step.round}: chat-completions request failed.`,
          detail,
        });
      }
      step.llmThought = answer.content ?? null;

      const toolCalls = answer.tool_calls ?? [];
      if (toolCalls.length === 0) {
        const content = answer.content?.trim();
        if (content) {
          trace.finalReply = content;
          return { reply: content, trace };
        }
        return fail("The chat model returned an empty reply.", {
          source: "llm",
          message: `Round ${step.round}: model returned no content and no tool calls.`,
          detail: "Empty choices[0].message with no tool_calls.",
        });
      }

      chatMessages.push({
        role: "assistant",
        content: answer.content ?? null,
        tool_calls: toolCalls,
      });

      for (const call of toolCalls) {
        const args = parseToolArguments(call.function.arguments);
        step.toolCalls.push({
          id: call.id,
          name: call.function.name,
          argumentsRaw: call.function.arguments,
          argumentsParsed: args,
        });
        let resultText: string;
        try {
          const result = await client.callTool({ name: call.function.name, arguments: args });
          const outcome = normalizeToolResult(call.function.name, result);
          resultText = renderOutcome(outcome);
          step.toolOutputs.push(
            outcome.ok
              ? { tool: outcome.tool, ok: true, renderedText: resultText, data: outcome.data }
              : { tool: outcome.tool, ok: false, renderedText: resultText, error: outcome.error },
          );
        } catch (error) {
          const detail = describeError(error);
          resultText = `That lookup failed: ${detail}`;
          step.toolOutputs.push({
            tool: call.function.name,
            ok: false,
            renderedText: resultText,
            error: { code: "error", message: resultText },
          });
        }
        chatMessages.push({ role: "tool", tool_call_id: call.id, content: resultText });
      }
    }

    return fail("The chat model did not finish within its tool budget.", {
      source: "llm",
      message: `Model kept calling tools for ${MAX_TOOL_ROUNDS} rounds without a final answer.`,
      detail: "Increase MAX_TOOL_ROUNDS or inspect the last step's tool outputs.",
    });
  });
}

const MAX_TOOL_ROUNDS = 5;

const CHAT_SYSTEM_PROMPT =
  "You are Alexa+, a concise study-planning assistant. " +
  "Answer from the study_* tool results when the user asks about their plan, tasks, " +
  "deadlines, courses, sources, or preferences; call the matching tool instead of " +
  "guessing. For greetings or small talk, reply directly without tools. " +
  "Keep replies short, plain-text (no Markdown headings), and grounded in what the " +
  "tools returned.";

type ChatCompletionMessage =
  | { role: "system"; content: string }
  | { role: "user"; content: string }
  | { role: "assistant"; content: string | null; tool_calls?: ChatToolCall[] }
  | { role: "tool"; tool_call_id: string; content: string };

type ChatToolCall = {
  id: string;
  type: "function";
  function: { name: string; arguments: string };
};

type LlmConfig = { baseUrl: string; apiKey: string; model: string };

/**
 * Resolves the OpenAI-compatible chat endpoint from the same `MODEL_*` settings
 * the Python backend uses. Returns null when no API key is configured.
 */
function getLlmConfig(): LlmConfig | null {
  const provider = (process.env.MODEL_PROVIDER?.trim() || "groq").toLowerCase();
  const model =
    process.env.MODEL_NAME?.trim() || process.env.GROQ_MODEL?.trim() || "openai/gpt-oss-120b";
  if (provider === "openrouter") {
    const apiKey = process.env.OPENROUTER_API_KEY?.trim();
    if (!apiKey) return null;
    return { baseUrl: "https://openrouter.ai/api/v1", apiKey, model };
  }
  if (provider === "openai") {
    const apiKey = process.env.OPENAI_API_KEY?.trim();
    if (!apiKey) return null;
    return { baseUrl: "https://api.openai.com/v1", apiKey, model };
  }
  const apiKey = process.env.GROQ_API_KEY?.trim();
  if (!apiKey || apiKey === "API_KEY") return null;
  return { baseUrl: "https://api.groq.com/openai/v1", apiKey, model };
}

async function completeChat(
  llm: LlmConfig,
  chatMessages: ChatCompletionMessage[],
  chatTools: Array<{
    type: "function";
    function: { name: string; description: string; parameters: Record<string, unknown> };
  }>,
): Promise<{ content: string | null; tool_calls?: ChatToolCall[] }> {
  let response: Response;
  try {
    response = await fetch(`${llm.baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${llm.apiKey}`,
      },
      body: JSON.stringify({
        model: llm.model,
        messages: chatMessages,
        tools: chatTools,
        tool_choice: "auto",
        temperature: 0,
      }),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (error) {
    throw new McpUnavailableError(`The chat model request failed: ${describeError(error)}`);
  }
  if (!response.ok) {
    throw new McpUnavailableError(`The chat model request failed with status ${response.status}.`);
  }
  const data = (await response.json()) as {
    choices?: Array<{ message?: { content?: string | null; tool_calls?: ChatToolCall[] } }>;
  };
  const message = data.choices?.[0]?.message;
  if (!message) {
    throw new McpUnavailableError("The chat model returned no message.");
  }
  return { content: message.content ?? null, tool_calls: message.tool_calls };
}

function parseToolArguments(raw: string): Record<string, unknown> {
  if (!raw) return {};
  try {
    const value: unknown = JSON.parse(raw);
    return value && typeof value === "object" && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

function renderOutcome(outcome: StudyToolOutcome): string {
  if (!outcome.ok) {
    return outcome.error.hint ? `${outcome.error.message} ${outcome.error.hint}` : outcome.error.message;
  }

  const data = outcome.data;

  if (Array.isArray(data.items) && data.items.length === 0) {
    return emptyReply(outcome.tool);
  }
  if (outcome.tool === "study_get_preferences") {
    return preferencesReply(data);
  }

  const summary = typeof data.markdown_summary === "string" ? data.markdown_summary.trim() : "";
  if (summary) {
    return toPlainText(summary);
  }

  // Structured content without a rendered summary (single-entity reads).
  const text = outcome.text?.trim();
  if (text) {
    return toPlainText(text);
  }
  return "I found the record but there is nothing to show yet.";
}

function emptyReply(tool: string): string {
  switch (tool) {
    case "study_list_academic_items":
      return "There are no academic items saved yet.";
    case "study_get_backlog":
      return "Your backlog is empty.";
    case "study_list_sources":
      return "No sources have been saved yet.";
    case "study_list_courses":
      return "No courses are registered yet.";
    case "study_list_tasks":
      return "You have no tasks yet.";
    case "study_get_changes_since":
      return "There is nothing new since then.";
    default:
      return "Nothing to show yet.";
  }
}

function preferencesReply(data: Record<string, unknown>): string {
  const minutes = data.preferred_daily_minutes;
  const focus = data.focus_task_count;
  if (minutes == null && focus == null) {
    return "You have not set planning preferences yet.";
  }
  const parts: string[] = [];
  if (minutes != null) parts.push(`${minutes} preferred daily minutes`);
  if (focus != null) parts.push(`${focus} focus tasks`);
  return `Your planning defaults: ${parts.join(" and ")}.`;
}

/** Removes light Markdown so a summary reads cleanly in a plain-text bubble. */
function toPlainText(markdown: string): string {
  return markdown
    .split("\n")
    .map((line) => line.replace(/^#{1,6}\s*/, "").replace(/\*\*(.+?)\*\*/g, "$1").trimEnd())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

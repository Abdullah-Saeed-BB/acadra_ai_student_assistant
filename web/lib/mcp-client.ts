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
 * Wall-clock budget for one MCP request/response round trip (connect, discovery,
 * or a tool call). Long-lived GET streams used for server push are not
 * time-boxed.
 */
const MCP_REQUEST_TIMEOUT_MS = 30_000;

/**
 * Chat-completions budget. This is intentionally separate from the MCP budget:
 * a model that is thinking through several tools can legitimately take longer
 * than a single MCP round trip, and the backend uses a 60-second model timeout.
 */
const LLM_REQUEST_TIMEOUT_MS = (() => {
  const configured = Number(process.env.LLM_REQUEST_TIMEOUT_MS ?? 60_000);
  return Number.isFinite(configured) && configured > 0 ? configured : 60_000;
})();

const BRIDGE_CLIENT_NAME = "acadra-web-bridge";
const BRIDGE_CLIENT_VERSION = "0.1.0";

export const MCP_SERVER_URL = (
  process.env.MCP_SERVER_URL?.trim() || DEFAULT_MCP_SERVER_URL
).replace(/\/+$/, "");

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
  | {
      tool: string;
      ok: true;
      data: Record<string, unknown>;
      text: string | null;
    }
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
  constructor(
    message = "The study planner MCP server is unavailable.",
    trace?: AgentTrace | null,
  ) {
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
  /** Tokens sent to the model (input) and produced by it (output) this round. */
  tokens: AgentTokenUsage;
};

export type AgentTokenUsage = {
  /** Tokens in the request (messages + tool schemas). Exact from API or estimated. */
  inputTokens: number;
  /** Tokens in the response (content + tool calls). Exact from API or estimated. */
  outputTokens: number;
  totalTokens: number;
  /** "api" = provider's usage block; "estimated" = ~chars/4 fallback. */
  source: "api" | "estimated";
  /** Raw provider numbers when the API returned them. */
  raw?: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null;
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
  /** Summed input/output across all recorded rounds. */
  totalTokens: AgentTokenUsage;
};

type McpToolResult = Awaited<ReturnType<Client["callTool"]>>;

/**
 * Wraps global `fetch` so request/response calls cannot hang. GET requests are
 * left alone because they carry the long-lived SSE stream; POST and DELETE calls
 * get a combined signal that still honours the transport's own abort.
 */
function createFetch(): (
  url: string | URL,
  init?: RequestInit,
) => Promise<Response> {
  return (url, init) => {
    const method = (init?.method ?? "GET").toUpperCase();
    if (method === "GET") {
      return fetch(url, init);
    }
    const timeout = AbortSignal.timeout(MCP_REQUEST_TIMEOUT_MS);
    const signal = init?.signal
      ? AbortSignal.any([init.signal, timeout])
      : timeout;
    return fetch(url, { ...init, signal });
  };
}

async function closeClient(
  client: Client,
  transport: StreamableHTTPClientTransport,
): Promise<void> {
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
async function withStudyClient<T>(
  run: (client: Client) => Promise<T>,
): Promise<T> {
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
    throw new McpUnavailableError(
      `The study planner MCP request failed: ${describeError(error)}`,
    );
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

function normalizeToolResult(
  tool: string,
  result: McpToolResult,
): StudyToolOutcome {
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

function extractError(
  parsed: Record<string, unknown> | null,
  rawText: string | null,
): StudyToolError {
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
    message:
      rawText?.trim() || "The study planner could not complete that request.",
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
export async function replyToConversation(
  messages: StudyChatMessage[],
): Promise<string> {
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
  const llms = getLlmConfigs();
  const llm = llms[0];
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
        detail:
          "Set MODEL_PROVIDER/MODEL_NAME plus its API key (GROQ_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY).",
      },
      totalTokens: zeroTokens(),
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
      totalTokens: zeroTokens(),
    };
    let activeLlms = llms;
    const fail = (message: string, error: AgentErrorTrace): never => {
      trace.error = error;
      throw new McpUnavailableError(message, trace);
    };

    let studyTools: Awaited<ReturnType<Client["listTools"]>>["tools"];
    try {
      ({ tools: studyTools } = await client.listTools());
    } catch (error) {
      return fail(
        `The study planner MCP request failed: ${describeError(error)}`,
        {
          source: "mcp",
          message: "tools/list failed.",
          detail: describeError(error),
        },
      );
    }
    const filtered = studyTools.filter((tool) =>
      tool.name.startsWith("study_"),
    );
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
      { role: "system", content: `${CHAT_SYSTEM_PROMPT} ${currentDateLine()}` },
      ...messages.map(
        (message): ChatCompletionMessage => ({
          role: message.role,
          content: message.text,
        }),
      ),
    ];

    const requiredByTool = new Map(
      filtered.map((tool) => [
        tool.name,
        Array.isArray((tool.inputSchema as { required?: unknown } | undefined)?.required)
          ? ((tool.inputSchema as { required: string[] }).required)
          : [],
      ]),
    );
    const readOnlyByTool = new Map(
      filtered.map((tool) => [
        tool.name,
        tool.annotations?.readOnlyHint === true,
      ]),
    );
    // Every successful write in this user turn. The final reply must not claim
    // a change that is absent from this list.
    const successfulWrites: AgentWriteRecord[] = [];
    // Repeating the exact same write in a later round cannot add information;
    // it only burns the tool budget. Reads are not deduplicated across rounds
    // because re-reading after a write is legitimate.
    const completedWriteSignatures = new Set<string>();
    // One corrective round is allowed when the model claims a write it did not
    // perform. That gives it a chance to call the missing tool instead of only
    // rewriting the text.
    let nudgedForMissingWrite = false;

    for (let round = 0; round < MAX_TOOL_ROUNDS; round += 1) {
      const step: AgentStepTrace = {
        round: round + 1,
        llmThought: null,
        toolCalls: [],
        toolOutputs: [],
        tokens: zeroTokens(),
      };
      trace.steps.push(step);

      // Estimate input BEFORE the call so a failed request still shows what was sent.
      const estimatedInput = estimateTokens(
        JSON.stringify(chatMessages) + JSON.stringify(chatTools),
      );
      let answer: {
        content: string | null;
        tool_calls?: ChatToolCall[];
        usage?: {
          prompt_tokens: number;
          completion_tokens: number;
          total_tokens: number;
        } | null;
      };
      try {
        const completed = await completeChatWithFallback(
          activeLlms,
          chatMessages,
          chatTools,
        );
        answer = completed.answer;
        if (completed.llm !== activeLlms[0]) {
          // Stick with the provider that worked so later rounds do not keep
          // retrying an exhausted key.
          activeLlms = [
            completed.llm,
            ...activeLlms.filter((candidate) => candidate !== completed.llm),
          ];
          trace.model = completed.llm.model;
        }
      } catch (error) {
        const detail = describeError(error);
        step.llmError = detail;
        step.tokens = {
          inputTokens: estimatedInput,
          outputTokens: 0,
          totalTokens: estimatedInput,
          source: "estimated",
          raw: null,
        };
        addTokens(trace.totalTokens, step.tokens);
        return fail(`The chat model request failed: ${detail}`, {
          source: "llm",
          message: `Round ${step.round}: chat-completions request failed.`,
          detail,
        });
      }
      step.llmThought = answer.content ?? null;
      step.tokens = toStepTokens(answer.usage ?? null, estimatedInput, answer);
      addTokens(trace.totalTokens, step.tokens);

      const toolCalls = answer.tool_calls ?? [];
      if (toolCalls.length === 0) {
        const content = answer.content?.trim();
        if (content) {
          const violations = verifyReplyClaims(content, successfulWrites);
          if (violations.length > 0 && !nudgedForMissingWrite) {
            nudgedForMissingWrite = true;
            chatMessages.push({ role: "assistant", content });
            chatMessages.push({
              role: "system",
              content:
                "Self-check: your previous reply claimed a change, but the tool " +
                `trace does not support it (${violations.join("; ")}). Do not ` +
                "repeat the claim. If the user asked for a change, call the " +
                "appropriate study_* write tool now. If no change is needed or " +
                "possible, rewrite the reply to say that nothing was changed. " +
                "Never claim a delete, merge, remove, or hide action.",
            });
            continue;
          }
          let finalReply = content;
          if (violations.length > 0) {
            const repaired = await repairReply(
              activeLlms,
              chatMessages,
              content,
              violations,
              successfulWrites,
              trace,
            );
            finalReply = repaired ?? safeFallbackReply(violations);
          }
          trace.finalReply = finalReply;
          return { reply: finalReply, trace };
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

      let lastSignature: string | null = null;
      for (const call of toolCalls) {
        const args = parseToolArguments(call.function.arguments);
        step.toolCalls.push({
          id: call.id,
          name: call.function.name,
          argumentsRaw: call.function.arguments,
          argumentsParsed: args,
        });

        // Guard: refuse empty/missing required arguments without an MCP round-trip.
        const required = requiredByTool.get(call.function.name) ?? [];
        const missing = required.filter((field) => {
          const value = args[field];
          return value === undefined || value === null || value === "";
        });
        const signature = `${call.function.name}:${JSON.stringify(args)}`;
        const isDuplicate = signature === lastSignature;
        const isRepeatedWrite =
          readOnlyByTool.get(call.function.name) !== true &&
          completedWriteSignatures.has(signature);

        let resultText: string;
        if (missing.length > 0) {
          resultText = `Invalid tool call: missing required argument(s): ${missing.join(", ")}. Provide them before calling ${call.function.name}.`;
          step.toolOutputs.push({
            tool: call.function.name,
            ok: false,
            renderedText: resultText,
            error: { code: "invalid_arguments", message: resultText },
          });
        } else if (isDuplicate || isRepeatedWrite) {
          resultText = `Skipped duplicate identical call to ${call.function.name}.`;
          step.toolOutputs.push({
            tool: call.function.name,
            ok: false,
            renderedText: resultText,
            error: { code: "duplicate_call", message: resultText },
          });
        } else {
          try {
            const result = await client.callTool({
              name: call.function.name,
              arguments: args,
            });
            const outcome = normalizeToolResult(call.function.name, result);
            resultText = renderOutcome(outcome);
            step.toolOutputs.push(
              outcome.ok
                ? {
                    tool: outcome.tool,
                    ok: true,
                    renderedText: resultText,
                    data: outcome.data,
                  }
                : {
                    tool: outcome.tool,
                    ok: false,
                    renderedText: resultText,
                    error: outcome.error,
                  },
            );
            if (outcome.ok && readOnlyByTool.get(outcome.tool) !== true) {
              completedWriteSignatures.add(signature);
              // Some write tools report that the requested value was already in
              // place. That is not a change, so it must not justify a claim.
              if (outcome.data.changed !== false) {
                successfulWrites.push({
                  tool: outcome.tool,
                  arguments: args,
                  data: outcome.data,
                });
              }
            }
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
        }
        lastSignature = signature;
        chatMessages.push({
          role: "tool",
          tool_call_id: call.id,
          content: resultText,
        });
      }
    }

    if (successfulWrites.length > 0) {
      // The writes succeeded even though the model never produced a closing
      // message. Returning a truthful summary is better than a 503.
      const reply =
        "I made the changes I could in your planner, but I hit my step limit " +
        "before I could summarize them. Ask me to show your plan and I'll " +
        "confirm what changed.";
      trace.finalReply = reply;
      return { reply, trace };
    }
    return fail("The chat model did not finish within its tool budget.", {
      source: "llm",
      message: `Model kept calling tools for ${MAX_TOOL_ROUNDS} rounds without a final answer.`,
      detail:
        "Increase MAX_TOOL_ROUNDS or inspect the last step's tool outputs.",
    });
  });
}

/**
 * Anchors relative dates to the same local calendar day the MCP server uses.
 * Without this, a model can infer "today" from UTC or from its own training
 * data and schedule "tonight" one day off.
 */
function currentDateLine(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  const weekday = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
  ][now.getDay()];
  return (
    `Today is ${year}-${month}-${day} (${weekday}) in the planner's local ` +
    "timezone. Use this date for 'today', 'tonight', 'tomorrow', and 'the day " +
    "after tomorrow'."
  );
}

/** A write tool that returned success (and, where reported, an actual change). */
type AgentWriteRecord = {
  tool: string;
  arguments: Record<string, unknown>;
  data: Record<string, unknown>;
};

/**
 * First-person past-tense write verbs. Refusals ("I can't delete or merge"),
 * hypotheticals ("I would update"), and read verbs ("I found") deliberately do
 * not match.
 */
function firstPersonPastClaim(text: string, verbs: string): boolean {
  return new RegExp(
    `\\b(?:i|i've|i have|i just)\\s+(?:${verbs})\\b` +
      `(?!\\s+(?:nothing|no|none|neither|anything))`,
    "i",
  ).test(text);
}

/**
 * Rejects a final reply that claims a change the tool trace does not support.
 *
 * This is deliberately narrow: it only checks first-person past-tense claims
 * and clear passive confirmations. That keeps refusals and explanations valid
 * while catching the two failure modes seen in practice: claiming a write that
 * never ran, and claiming a delete/merge that no tool can perform.
 */
function verifyReplyClaims(
  reply: string,
  writes: AgentWriteRecord[],
): string[] {
  const problems: string[] = [];
  const text = reply.trim();
  if (!text) return problems;

  const unsupportedClaims = [
    // "I removed nothing" and "I deleted none of them" are clear refusals.
    /\b(?:i|i've|i have|i just)\s+(?:deleted|removed|erased|merged|hid|hidden)\b(?!\s+(?:nothing|no|none|neither|anything))\b/i,
    /\b(?:the|that|this)\s+(?:duplicate|extra|record|entry|source|page|task)\s+(?:is|was|has been|has now been)\s+(?:deleted|removed|merged|hidden)\b/i,
    /\bmerged!\b/i,
  ];
  if (unsupportedClaims.some((pattern) => pattern.test(text))) {
    problems.push(
      "the reply claims a delete, merge, remove, or hide action, but the planner has no such tool",
    );
    return problems;
  }

  const writeTools = new Set(writes.map((write) => write.tool));
  if (
    firstPersonPastClaim(
      text,
      "created|added|updated|changed|moved|rescheduled|completed|marked|renamed|edited|modified|set|saved|linked|unlinked|split",
    ) &&
    writeTools.size === 0
  ) {
    problems.push(
      "the reply claims a change, but no write tool succeeded in this turn",
    );
    return problems;
  }

  if (
    /\b(?:i|i've|i have|i just)\s+(?:set|saved|updated|changed)\b[^.!?]{0,60}\b(?:daily (?:limit|minutes)|focus tasks?|planning (?:defaults|preferences))\b/i.test(
      text,
    ) &&
    !writeTools.has("study_set_preferences")
  ) {
    problems.push(
      "the reply claims a preferences change, but study_set_preferences did not succeed",
    );
  }

  if (
    /\b(?:i|i've|i have|i just)\s+(?:created|added)\b[^.!?]{0,60}\b(?:task|block|step|entry)\b/i.test(
      text,
    ) &&
    !["study_create_task", "study_split_task", "study_add_manual_text"].some(
      (tool) => writeTools.has(tool),
    )
  ) {
    problems.push(
      "the reply claims a creation, but no create tool succeeded in this turn",
    );
  }

  if (
    /\b(?:i|i've|i have|i just)\s+(?:completed|marked)\b[^.!?]{0,60}\b(?:done|complete)\b/i.test(
      text,
    ) &&
    !writeTools.has("study_complete_task") &&
    !writes.some(
      (write) =>
        write.tool === "study_update_task" && write.arguments.status === "done",
    )
  ) {
    problems.push(
      "the reply claims a completion, but no completion write succeeded in this turn",
    );
  }

  return problems;
}

function safeFallbackReply(violations: string[]): string {
  if (violations.some((violation) => violation.includes("delete, merge"))) {
    return (
      "I can't delete or merge records, so nothing was removed. " +
      "I can update, move, reschedule, or complete a task instead."
    );
  }
  return (
    "I wasn't able to make that change, so nothing was updated. " +
    "Let me know if you want me to try again."
  );
}

/**
 * Asks the model once to rewrite a reply using only the writes that actually
 * succeeded. Returns null when the rewrite fails or still makes an unsupported
 * claim, so the caller can use a deterministic fallback.
 */
async function repairReply(
  llms: LlmConfig[],
  chatMessages: ChatCompletionMessage[],
  previousReply: string,
  violations: string[],
  writes: AgentWriteRecord[],
  trace: AgentTrace,
): Promise<string | null> {
  const step: AgentStepTrace = {
    round: trace.steps.length + 1,
    llmThought: null,
    toolCalls: [],
    toolOutputs: [],
    tokens: zeroTokens(),
  };
  trace.steps.push(step);

  const successfulTools = writes.map((write) => write.tool);
  const instruction =
    "Your previous reply claimed a change that the tool results do not support. " +
    "Rewrite it so it is strictly true, without mentioning this instruction. " +
    `Problems: ${violations.join("; ")}. ` +
    `Successful writes in this turn: ${
      successfulTools.length > 0 ? [...new Set(successfulTools)].join(", ") : "none"
    }. ` +
    "If no write succeeded, say that nothing was changed. " +
    "Never claim to have deleted, merged, removed, or hidden anything: those tools do not exist. " +
    "Keep the same helpful tone and stay within 1-3 short sentences.";

  const repairMessages: ChatCompletionMessage[] = [
    ...chatMessages,
    { role: "assistant", content: previousReply },
    { role: "system", content: instruction },
  ];
  const estimatedInput = estimateTokens(
    JSON.stringify(repairMessages) + instruction,
  );

  try {
    const { answer } = await completeChatWithFallback(
      llms,
      repairMessages,
      [],
    );
    step.llmThought = answer.content ?? null;
    step.tokens = toStepTokens(answer.usage ?? null, estimatedInput, answer);
    addTokens(trace.totalTokens, step.tokens);
    const content = answer.content?.trim();
    if (!content) return null;
    return verifyReplyClaims(content, writes).length === 0 ? content : null;
  } catch (error) {
    step.llmError = describeError(error);
    step.tokens = {
      inputTokens: estimatedInput,
      outputTokens: 0,
      totalTokens: estimatedInput,
      source: "estimated",
      raw: null,
    };
    addTokens(trace.totalTokens, step.tokens);
    return null;
  }
}

const MAX_TOOL_ROUNDS = 10;

const CHAT_SYSTEM_PROMPT =
  "You are Alexa+, a friendly study-planning assistant inside the Acadra app. Be warm and conversational, " +
  "like a helpful friend. Keep replies brief by default: 1-3 short sentences, no deep " +
  "detail unless the user explicitly asks for details. If the user asks for details, " +
  "give them but stay concise and skip extra background. " +
  "Use plain text only: never use Markdown, headings, titles, bold, italics, bullet " +
  "or numbered lists, or code blocks; write in natural sentences and join items with " +
  "commas and 'and'. " +
  "Answer from the study_* tool results when the user asks about their plan, tasks, " +
  "deadlines, courses, sources, or preferences; call the matching tool instead of " +
  "guessing. For greetings or small talk, reply directly without tools. " +
  "Stay grounded in what the tools returned. " +
  "App vocabulary: " +
  "The Acadra app has its own Inbox page. When the user says 'inbox', 'my inbox', " +
  "or asks what is new in the inbox, they mean the Acadra Inbox: recent academic " +
  "items and the academic-item change feed. Answer with study_get_changes_since " +
  "for recent changes and study_list_academic_items for recent items; call " +
  "study_list_courses only if you need course names. " +
  "Gmail is only one external source. study_get_gmail_connection and " +
  "study_set_gmail_senders report or change the Gmail connection and sender " +
  "allowlist; they do not read an inbox or messages, so never use them for an " +
  "inbox request. Likewise, map Today, Plan, Backlog, Courses, and Sources to " +
  "the matching study_* reads rather than to an external service with a similar " +
  "name. If a request is ambiguous, prefer the Acadra page or feature name over " +
  "an external provider concept. " +
  "Planning rules: " +
  "1) Before creating a task, call study_list_tasks or study_get_today_plan to check " +
  "for an existing similar task; if one exists, reuse or update it instead of " +
  "creating a duplicate. " +
  "2) Never call study_create_task without title, selected_day, and estimated_minutes. " +
  "3) When the user corrects which item they mean (for example first quiz to second " +
  "quiz), do not mention or act on the earlier or already-past item. " +
  "4) For 'tomorrow' use the day after today; for 'tonight' use today. " +
  "5) Answer 'final exam date' from the academic item whose title contains 'Final exam'. " +
  "6) Do not echo academic items that are already past unless the user asks. " +
  "Capability boundaries: " +
  "The planner has no tool to delete or merge tasks, academic items, or sources. " +
  "Never delete, merge, remove, hide, or claim to have done any of those things. " +
  "study_review_academic_item only changes an item's review state; it never deletes, " +
  "merges, hides, or removes the item, so never use it to satisfy a delete or merge request. " +
  "Do not emulate an unsupported operation by completing a task, rejecting an item, " +
  "renaming it, moving it out of the way, or creating a replacement. " +
  "When the user asks for an unsupported operation, say plainly that you cannot delete " +
  "or merge records, name the record you are leaving unchanged, do not perform a " +
  "different write, and do not describe marking a task done as deleting or merging it. " +
  "Truthfulness: only say that a change happened after the matching write tool returned " +
  "success in this turn. If the tool result shows no change, say that no change was made. " +
  "When you refer to a specific record, name it by its title. " +
  "Correction continuity: when the user corrects a task you just created or updated in " +
  "this conversation, reuse that task's id and update it in place; do not create a second " +
  "task and do not keep the old one as a renamed leftover.";

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

type ChatTool = {
  type: "function";
  function: {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
  };
};

type ChatAnswer = {
  content: string | null;
  tool_calls?: ChatToolCall[];
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null;
};

type LlmConfig = { baseUrl: string; apiKey: string; model: string };

/**
 * Resolves the OpenAI-compatible chat endpoints from the same `MODEL_*`
 * settings the Python backend uses. The configured provider comes first; when
 * Groq is not the primary and has a key, it is appended as a fallback so an
 * exhausted or unavailable primary key does not take the whole bridge down.
 */
function getLlmConfigs(): LlmConfig[] {
  const provider = (process.env.MODEL_PROVIDER?.trim() || "groq").toLowerCase();
  const model =
    process.env.MODEL_NAME?.trim() ||
    process.env.GROQ_MODEL?.trim() ||
    "openai/gpt-oss-120b";
  const fallbackModel =
    process.env.MODEL_FALLBACK_NAME?.trim() || "openai/gpt-oss-120b";
  const configs: LlmConfig[] = [];

  const add = (baseUrl: string, apiKey: string | undefined, modelName: string) => {
    const trimmed = apiKey?.trim();
    if (!trimmed || trimmed === "API_KEY") return;
    if (configs.some((config) => config.baseUrl === baseUrl && config.model === modelName)) {
      return;
    }
    configs.push({ baseUrl, apiKey: trimmed, model: modelName });
  };

  if (provider === "openrouter") {
    add("https://openrouter.ai/api/v1", process.env.OPENROUTER_API_KEY, model);
  } else if (provider === "deepseek") {
    add("https://api.deepseek.com", process.env.DEEPSEEK_API_KEY, model);
  } else if (provider === "openai") {
    add("https://api.openai.com/v1", process.env.OPENAI_API_KEY, model);
  } else {
    add("https://api.groq.com/openai/v1", process.env.GROQ_API_KEY, model);
  }

  if (provider !== "groq") {
    add(
      "https://api.groq.com/openai/v1",
      process.env.GROQ_API_KEY,
      fallbackModel,
    );
  }
  return configs;
}

/**
 * Hard per-attempt timeout covering both the response headers and the body.
 * `AbortSignal.timeout` alone is usually enough, but a transport that ignores
 * the signal would otherwise leave a turn hanging for minutes. The race
 * guarantees the caller gets control back at the deadline.
 */
async function fetchTextWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<{ response: Response; text: string }> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timedOut = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(new Error(`request timed out after ${timeoutMs}ms`));
    }, timeoutMs);
  });
  const request = (async () => {
    const response = await fetch(url, { ...init, signal: controller.signal });
    const text = await response.text();
    return { response, text };
  })();
  try {
    return await Promise.race([request, timedOut]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

async function completeChat(
  llm: LlmConfig,
  chatMessages: ChatCompletionMessage[],
  chatTools: ChatTool[],
): Promise<ChatAnswer> {
  const maxRetries = Math.max(
    0,
    Number(process.env.MODEL_MAX_RETRIES ?? 2) || 0,
  );
  const startedAt = Date.now();
  const attempts = maxRetries + 1;
  let lastError: unknown = null;
  const body = JSON.stringify({
    model: llm.model,
    messages: chatMessages,
    temperature: 0,
    ...(chatTools.length > 0
      ? { tools: chatTools, tool_choice: "auto" as const }
      : {}),
  });

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    let response: Response;
    let responseText: string;
    try {
      ({ response, text: responseText } = await fetchTextWithTimeout(
        `${llm.baseUrl}/chat/completions`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${llm.apiKey}`,
          },
          body,
        },
        LLM_REQUEST_TIMEOUT_MS,
      ));
    } catch (error) {
      lastError = error;
      const detail = describeError(error);
      console.error(
        `[mcp-client] model=${llm.model} chat-completions network error ` +
          `(attempt ${attempt + 1}/${attempts}) after ${Date.now() - startedAt}ms: ${detail}`,
      );
      if (attempt + 1 < attempts) {
        await sleep(retryDelayMs(attempt));
        continue;
      }
      throw new McpUnavailableError(
        `The chat model request failed after ${attempts} attempt(s): ${detail}`,
      );
    }

    if (!response.ok) {
      const snippet = sanitizeProviderBody(responseText);
      lastError = new Error(`HTTP ${response.status}: ${snippet}`);
      console.error(
        `[mcp-client] model=${llm.model} chat-completions HTTP ${response.status} ` +
          `(attempt ${attempt + 1}/${attempts}) after ${Date.now() - startedAt}ms: ${snippet}`,
      );
      if (attempt + 1 < attempts && isTransientStatus(response.status)) {
        await sleep(retryDelayMs(attempt, response));
        continue;
      }
      throw new McpUnavailableError(
        `The chat model request failed with status ${response.status}` +
          (snippet ? `: ${snippet}` : "."),
      );
    }

    let data: {
      choices?: Array<{
        message?: { content?: string | null; tool_calls?: ChatToolCall[] };
      }>;
      usage?: {
        prompt_tokens?: unknown;
        completion_tokens?: unknown;
        total_tokens?: unknown;
      } | null;
    };
    try {
      data = JSON.parse(responseText) as typeof data;
    } catch {
      lastError = new Error("the provider returned malformed JSON");
      console.error(
        `[mcp-client] model=${llm.model} chat-completions returned malformed JSON ` +
          `(attempt ${attempt + 1}/${attempts}) after ${Date.now() - startedAt}ms`,
      );
      if (attempt + 1 < attempts) {
        await sleep(retryDelayMs(attempt));
        continue;
      }
      throw new McpUnavailableError(
        "The chat model returned a malformed JSON response.",
      );
    }
    const message = data.choices?.[0]?.message;
    if (!message) {
      lastError = new Error("the provider returned no message");
      console.error(
        `[mcp-client] model=${llm.model} chat-completions returned no message ` +
          `(attempt ${attempt + 1}/${attempts}) after ${Date.now() - startedAt}ms`,
      );
      if (attempt + 1 < attempts) {
        await sleep(retryDelayMs(attempt));
        continue;
      }
      throw new McpUnavailableError("The chat model returned no message.");
    }
    console.log(
      `[mcp-client] model=${llm.model} chat-completions ok in ` +
        `${Date.now() - startedAt}ms (attempt ${attempt + 1}/${attempts}` +
        `${message.tool_calls?.length ? `, ${message.tool_calls.length} tool call(s)` : ""})`,
    );
    return {
      content: message.content ?? null,
      tool_calls: message.tool_calls,
      usage: normalizeUsage(data.usage),
    };
  }
  throw new McpUnavailableError(
    `The chat model request failed: ${describeError(lastError)}`,
  );
}

/**
 * Tries each configured provider in order. A primary key that is exhausted or
 * rejected must not take the whole bridge down when a fallback is configured.
 */
async function completeChatWithFallback(
  llms: LlmConfig[],
  chatMessages: ChatCompletionMessage[],
  chatTools: ChatTool[],
): Promise<{ answer: ChatAnswer; llm: LlmConfig }> {
  let lastError: unknown = null;
  const failures: string[] = [];
  for (const candidate of llms) {
    try {
      const answer = await completeChat(candidate, chatMessages, chatTools);
      return { answer, llm: candidate };
    } catch (error) {
      lastError = error;
      failures.push(`${candidate.model}: ${describeError(error)}`);
      console.error(
        `[mcp-client] model=${candidate.model} failed; trying the next configured provider if any: ${describeError(error)}`,
      );
    }
  }
  if (failures.length > 1) {
    throw new McpUnavailableError(
      `Every configured chat model failed: ${failures.join(" | ")}`,
    );
  }
  throw lastError instanceof Error
    ? lastError
    : new McpUnavailableError("Every configured chat model failed.");
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Transient provider failures worth retrying; 400/401/403 are not. */
function isTransientStatus(status: number): boolean {
  return status === 408 || status === 409 || status === 425 || status === 429 || status >= 500;
}

/**
 * Backoff with jitter. Honors `Retry-After` (seconds or HTTP date) so a rate
 * limit is not hammered, but caps the wait so one turn cannot hang the bridge.
 */
function retryDelayMs(attempt: number, response?: Response): number {
  const retryAfter = response?.headers.get("retry-after")?.trim();
  if (retryAfter) {
    const seconds = Number(retryAfter);
    if (Number.isFinite(seconds) && seconds >= 0) {
      return Math.min(seconds * 1000, 10_000);
    }
    const when = Date.parse(retryAfter);
    if (Number.isFinite(when)) {
      return Math.min(Math.max(when - Date.now(), 0), 10_000);
    }
  }
  const base = Math.min(500 * 2 ** attempt, 4_000);
  return base + Math.floor(Math.random() * 250);
}

function sanitizeProviderBody(body: string): string {
  return body.replace(/\s+/g, " ").trim().slice(0, 300);
}

/** Pulls exact token counts out of the provider's `usage` block, if present. */
function normalizeUsage(
  usage:
    | {
        prompt_tokens?: unknown;
        completion_tokens?: unknown;
        total_tokens?: unknown;
      }
    | null
    | undefined,
): {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
} | null {
  if (!usage) return null;
  const prompt =
    typeof usage.prompt_tokens === "number" ? usage.prompt_tokens : NaN;
  const completion =
    typeof usage.completion_tokens === "number"
      ? usage.completion_tokens
      : NaN;
  const total =
    typeof usage.total_tokens === "number" ? usage.total_tokens : NaN;
  if (!Number.isFinite(prompt) || !Number.isFinite(completion)) return null;
  return {
    prompt_tokens: prompt,
    completion_tokens: completion,
    total_tokens: Number.isFinite(total) ? total : prompt + completion,
  };
}

function zeroTokens(): AgentTokenUsage {
  return {
    inputTokens: 0,
    outputTokens: 0,
    totalTokens: 0,
    source: "api",
    raw: null,
  };
}

/**
 * Rough token estimate (~4 chars per token) used only when the provider
 * omits its `usage` block. Keeps the viewer honest: exact when possible,
 * approximate otherwise.
 */
function estimateTokens(text: string): number {
  const len = text.trim().length;
  if (len === 0) return 0;
  return Math.max(1, Math.ceil(len / 4));
}

function toStepTokens(
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null,
  estimatedInput: number,
  answer: { content: string | null; tool_calls?: ChatToolCall[] },
): AgentTokenUsage {
  if (usage) {
    return {
      inputTokens: usage.prompt_tokens,
      outputTokens: usage.completion_tokens,
      totalTokens: usage.total_tokens,
      source: "api",
      raw: usage,
    };
  }
  const estimatedOutput = estimateTokens(
    (answer.content ?? "") + JSON.stringify(answer.tool_calls ?? []),
  );
  return {
    inputTokens: estimatedInput,
    outputTokens: estimatedOutput,
    totalTokens: estimatedInput + estimatedOutput,
    source: "estimated",
    raw: null,
  };
}

function addTokens(total: AgentTokenUsage, step: AgentTokenUsage): void {
  const pristine =
    total.inputTokens === 0 &&
    total.outputTokens === 0 &&
    total.totalTokens === 0;
  if (pristine) total.source = step.source;
  else if (step.source !== "api" || total.source !== "api")
    total.source = "estimated";
  total.inputTokens += step.inputTokens;
  total.outputTokens += step.outputTokens;
  total.totalTokens += step.totalTokens;
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
    return outcome.error.hint
      ? `${outcome.error.message} ${outcome.error.hint}`
      : outcome.error.message;
  }

  const data = outcome.data;

  if (Array.isArray(data.items) && data.items.length === 0) {
    return emptyReply(outcome.tool);
  }
  if (outcome.tool === "study_get_preferences") {
    return preferencesReply(data);
  }

  const summary =
    typeof data.markdown_summary === "string"
      ? data.markdown_summary.trim()
      : "";
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
    .map((line) =>
      line
        .replace(/^#{1,6}\s*/, "")
        .replace(/\*\*(.+?)\*\*/g, "$1")
        .trimEnd(),
    )
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

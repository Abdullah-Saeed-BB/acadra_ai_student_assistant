/**
 * TEMP DEBUG COMPONENT — TempAgentTrace
 * ======================
 * A temporary, self-contained viewer for the AI agent process. Drop it under an
 * assistant bubble to inspect thoughts, tool calls, tool outputs, and full
 * error logs. Everything renders with native <details> (collapsed by default)
 * and inline styles, so deleting this file removes all of its UI.
 *
 * ---------------------------------------------------------------------------
 * WHAT I CHANGED OUTSIDE THIS FILE (revert these to restore original code):
 * ---------------------------------------------------------------------------
 * 1. app/web/lib/mcp-client.ts
 *    - Added trace types: AgentToolCallTrace, AgentToolOutputTrace,
 *      AgentStepTrace, AgentErrorTrace, AgentTrace.
 *    - `McpUnavailableError` gained an optional `agentTrace` field.
 *    - Added `replyWithTrace()` which records every LLM round (thought,
 *      tool calls, tool outputs, llmError) plus model/MCP URL/tools list.
 *    - `replyToConversation()` is now a thin wrapper around `replyWithTrace()`.
 *    - Fixed `chatTools` to map over the filtered `study_*` tools.
 *    TO REVERT: delete the trace types + `replyWithTrace`, restore the old
 *    `replyToConversation` body and the plain `McpUnavailableError`.
 *
 * 2. app/web/app/api/alexa-chat/route.ts
 *    - Switched import to `replyWithTrace`; success returns `{ reply, trace }`.
 *    - 503 now returns `{ error, trace: error.agentTrace ?? null }`;
 *      500 returns `{ error, trace: null }`.
 *    TO REVERT: import `replyToConversation` again and return `{ reply }` /
 *    `{ error }` without `trace`.
 *
 * 3. app/web/app/alexa+_simulator/alexa-transport.ts
 *    - Added `BridgeResult` + `FrontendErrorTrace` types.
 *    - Added `requestAlexaWithTrace()` (captures fetch throw, non-JSON body,
 *      non-2xx status, empty reply as structured frontendError + server trace).
 *    - `requestAlexaReply()` and `requestFromBridge()` delegate to it.
 *    TO REVERT: restore the old file that only exported `requestAlexaReply`
 *    returning `string` with a null-on-failure `requestFromBridge`.
 *
 * 4. app/web/app/alexa+_simulator/alexa-simulator.tsx
 *    - Assistant messages now carry `trace`, `frontendError`, `durationMs`.
 *    - `send()` calls `requestAlexaWithTrace()` and renders <TempAgentTrace>.
 *    - Error banner shows the structured error message instead of a generic one.
 *    TO REVERT: restore `ChatMessage[]` state, `requestAlexaReply` call, and
 *    remove the <TempAgentTrace> render + its import.
 *
 * 5. system/STRUCTURE_FRONTEND.md (repo rule: new file under app/web/ must be listed)
 *    - Added `components/temp-agent-trace.tsx` line.
 *    TO REVERT: remove that line.
 *
 * DELETE THIS FILE + the 4 reverts above = back to original code.
 */

"use client";

import type { AgentTrace } from "@/lib/mcp-client";
import type { FrontendErrorTrace } from "@/app/alexa+_simulator/alexa-transport";

export type TempAgentTraceProps = {
  trace: AgentTrace | null;
  frontendError?: FrontendErrorTrace | null;
  durationMs?: number | null;
};

function countToolCalls(trace: AgentTrace | null): number {
  if (!trace) return 0;
  return trace.steps.reduce((n, s) => n + s.toolCalls.length, 0);
}

function shortSummary(trace: AgentTrace | null, frontendError?: FrontendErrorTrace | null): string {
  const serverErr = trace?.error;
  if (frontendError && trace) return `agent trace + bridge error (${trace.steps.length} round${trace.steps.length === 1 ? "" : "s"})`;
  if (frontendError) return "frontend / bridge error — no agent trace";
  if (!trace) return "no trace";
  if (serverErr) return `agent error (${trace.steps.length} round${trace.steps.length === 1 ? "" : "s"})`;
  if (trace.steps.length === 0) return "direct answer (no tools)";
  return `${trace.steps.length} round${trace.steps.length === 1 ? "" : "s"} · ${countToolCalls(trace)} tool call${countToolCalls(trace) === 1 ? "" : "s"}`;
}

const box: React.CSSProperties = {
  marginTop: 8,
  border: "1px dashed #b3c4c0",
  borderRadius: 10,
  background: "#f2f6f5",
  fontSize: 13,
  lineHeight: 1.5,
};

const summaryRow: React.CSSProperties = {
  cursor: "pointer",
  padding: "8px 12px",
  fontWeight: 700,
  color: "#0a665e",
  listStyle: "none",
};

const section: React.CSSProperties = {
  borderTop: "1px solid #b3c4c0",
  padding: "8px 12px",
};

const pre: React.CSSProperties = {
  margin: "6px 0 0",
  padding: "8px 10px",
  background: "#142e36",
  color: "#e8f1ee",
  borderRadius: 6,
  fontSize: 12,
  whiteSpace: "pre-wrap",
  overflowWrap: "anywhere",
  maxHeight: 260,
  overflow: "auto",
};

const badge = (ok: boolean): React.CSSProperties => ({
  display: "inline-block",
  padding: "1px 8px",
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 700,
  background: ok ? "rgba(10,102,94,.12)" : "rgba(150,53,44,.12)",
  color: ok ? "#0a665e" : "#96352c",
  marginLeft: 8,
});

const label: React.CSSProperties = { color: "#43585e", fontWeight: 600 };

function CopyJsonButton({ value }: { value: unknown }) {
  async function copy() {
    try {
      await navigator.clipboard.writeText(JSON.stringify(value, null, 2));
    } catch {
      // clipboard unavailable (non-secure context); ignore silently
    }
  }
  return (
    <button
      type="button"
      onClick={copy}
      style={{
        marginLeft: 8,
        padding: "1px 10px",
        fontSize: 12,
        fontWeight: 600,
        border: "1px solid #b3c4c0",
        borderRadius: 6,
        background: "#fff",
        cursor: "pointer",
      }}
    >
      copy JSON
    </button>
  );
}

export function TempAgentTrace({ trace, frontendError, durationMs }: TempAgentTraceProps) {
  const hasServerError = Boolean(trace?.error);
  const hasFrontendError = Boolean(frontendError);
  const dot = hasFrontendError || hasServerError ? "🔴" : "🟢";

  return (
    <details style={box} data-testid="temp-agent-trace">
      <summary style={summaryRow}>
        {dot} agent trace — {shortSummary(trace, frontendError)}
        {typeof durationMs === "number" && (
          <span style={{ color: "#43585e", fontWeight: 400 }}> · {durationMs}ms</span>
        )}
      </summary>

      {/* ---- run overview ---- */}
      <div style={section}>
        <div>
          <span style={label}>model: </span>
          <code>{trace?.model ?? "(none — bridge never reached the LLM)"}</code>
        </div>
        <div>
          <span style={label}>mcp: </span>
          <code>{trace?.mcpServerUrl ?? "(unknown)"}</code>
        </div>
        <div>
          <span style={label}>tools discovered ({trace?.toolsDiscovered.length ?? 0}): </span>
          <code>{trace && trace.toolsDiscovered.length > 0 ? trace.toolsDiscovered.join(", ") : "—"}</code>
        </div>
        {trace?.finalReply ? (
          <div style={{ marginTop: 4 }}>
            <span style={label}>final reply: </span>
            <span>{trace.finalReply.slice(0, 160)}{trace.finalReply.length > 160 ? "…" : ""}</span>
          </div>
        ) : null}
        <CopyJsonButton value={{ trace, frontendError }} />
      </div>

      {/* ---- per-round thinking ---- */}
      {trace && trace.steps.length > 0 ? (
        <div style={section}>
          <div style={label}>rounds ({trace.steps.length}) — open each to see thought → tools → outputs</div>
          {trace.steps.map((step) => (
            <details key={step.round} style={{ marginTop: 6, border: "1px solid #b3c4c0", borderRadius: 8, background: "#fff" }}>
              <summary style={{ cursor: "pointer", padding: "6px 10px", fontWeight: 700 }}>
                round {step.round}
                <span style={badge(step.toolCalls.length === 0)}>
                  {step.toolCalls.length === 0 ? "no tool call" : `${step.toolCalls.length} tool call${step.toolCalls.length === 1 ? "" : "s"}`}
                </span>
                {step.llmError && <span style={badge(false)}>llm error</span>}
              </summary>
              <div style={{ padding: "6px 10px 10px" }}>
                <div style={label}>① LLM thought / draft (raw content)</div>
                {step.llmThought ? <pre style={pre}>{step.llmThought}</pre> : <p style={{ margin: "4px 0" }}>— (empty: model said nothing before acting)</p>}

                <div style={{ ...label, marginTop: 8 }}>② tool calls (the model&apos;s decisions)</div>
                {step.toolCalls.length === 0 ? (
                  <p style={{ margin: "4px 0" }}>— none this round (direct answer or small talk).</p>
                ) : (
                  step.toolCalls.map((call) => (
                    <details key={call.id} style={{ marginTop: 6 }}>
                      <summary style={{ cursor: "pointer" }}>
                        <code>{call.name}</code> <span style={{ color: "#43585e" }}>id={call.id}</span>
                      </summary>
                      <div style={label}>arguments (parsed)</div>
                      <pre style={pre}>{JSON.stringify(call.argumentsParsed, null, 2)}</pre>
                      {call.argumentsRaw && (
                        <>
                          <div style={label}>arguments (raw string)</div>
                          <pre style={pre}>{call.argumentsRaw}</pre>
                        </>
                      )}
                    </details>
                  ))
                )}

                <div style={{ ...label, marginTop: 8 }}>③ tool outputs (what was fed back to the LLM)</div>
                {step.toolOutputs.length === 0 ? (
                  <p style={{ margin: "4px 0" }}>— none (no tools ran this round).</p>
                ) : (
                  step.toolOutputs.map((out, i) => (
                    <details key={`${out.tool}-${i}`} style={{ marginTop: 6 }} open={out.ok === false}>
                      <summary style={{ cursor: "pointer" }}>
                        <code>{out.tool}</code>
                        <span style={badge(out.ok)}>{out.ok ? "ok" : "failed"}</span>
                      </summary>
                      <pre style={pre}>{out.renderedText || "— (empty output)"}</pre>
                      {out.error && (
                        <>
                          <div style={label}>error envelope</div>
                          <pre style={pre}>{JSON.stringify(out.error, null, 2)}</pre>
                        </>
                      )}
                      {out.data && Object.keys(out.data).length > 0 && (
                        <>
                          <div style={label}>raw data keys: {Object.keys(out.data).join(", ")}</div>
                          <pre style={pre}>{JSON.stringify(out.data, null, 2).slice(0, 3000)}</pre>
                        </>
                      )}
                    </details>
                  ))
                )}
                {/* The next round's "LLM thought" IS the model's reaction to the outputs above. */}

                {step.llmError && (
                  <>
                    <div style={{ ...label, marginTop: 8 }}>round LLM error</div>
                    <pre style={pre}>{step.llmError}</pre>
                  </>
                )}
              </div>
            </details>
          ))}
        </div>
      ) : (
        <div style={section}>
          <span style={label}>rounds: </span>— (no LLM rounds recorded; the failure happened before the loop)
        </div>
      )}

      {/* ---- server-side error (bridge / MCP / LLM) ---- */}
      <details style={section} open={hasServerError}>
        <summary style={{ cursor: "pointer", fontWeight: 700 }}>
          {hasServerError ? "🔴" : "🟢"} server error log (bridge / MCP / LLM)
        </summary>
        {trace?.error ? (
          <>
            <div><span style={label}>source: </span><code>{trace.error.source}</code></div>
            <div><span style={label}>message: </span>{trace.error.message}</div>
            {trace.error.detail && <pre style={pre}>{trace.error.detail}</pre>}
          </>
        ) : (
          <p style={{ margin: "4px 0" }}>— none. The server loop finished without recording an error.</p>
        )}
      </details>

      {/* ---- frontend / HTTP error ---- */}
      <details style={section} open={hasFrontendError}>
        <summary style={{ cursor: "pointer", fontWeight: 700 }}>
          {hasFrontendError ? "🔴" : "🟢"} frontend / HTTP error log
        </summary>
        {frontendError ? (
          <>
            <div><span style={label}>source: </span><code>{frontendError.source}</code> (frontend = browser fetch failed · bridge-http = /api/alexa-chat answered badly)</div>
            <div><span style={label}>message: </span>{frontendError.message}</div>
            {typeof frontendError.status === "number" && (
              <div><span style={label}>http status: </span><code>{frontendError.status}</code></div>
            )}
            {frontendError.detail && <pre style={pre}>{frontendError.detail}</pre>}
            {frontendError.rawBody && (
              <>
                <div style={label}>raw bridge body</div>
                <pre style={pre}>{frontendError.rawBody}</pre>
              </>
            )}
          </>
        ) : (
          <p style={{ margin: "4px 0" }}>— none. The browser got a 200 with a non-empty reply.</p>
        )}
      </details>

      {/* ---- raw dump ---- */}
      <details style={section}>
        <summary style={{ cursor: "pointer", fontWeight: 700 }}>raw trace JSON</summary>
        <pre style={pre}>{JSON.stringify(trace ?? null, null, 2)}</pre>
      </details>
    </details>
  );
}

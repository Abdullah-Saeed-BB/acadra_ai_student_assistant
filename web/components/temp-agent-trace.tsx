/**
 * Agent trace viewer for the AI assistant process.
 *
 * Default view is friendly and concise for non-technical users. Toggle
 * "Dev mode" to reveal the full technical details (rounds, tool calls,
 * arguments, outputs, tokens, raw JSON).
 */

"use client";

import { useState } from "react";
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

function formatNum(n: number): string {
  return n.toLocaleString("en-US");
}

function friendlyToolName(name: string): string {
  const map: Record<string, string> = {
    study_list_tasks: "checked your tasks",
    study_create_task: "created a task",
    study_update_task: "updated a task",
    study_complete_task: "marked a task done",
    study_split_task: "split a task",
    study_get_today_plan: "checked today's plan",
    study_get_backlog: "checked your backlog",
    study_list_academic_items: "checked your academic items",
    study_review_academic_item: "reviewed an academic item",
    study_list_sources: "checked your sources",
    study_add_manual_text: "added a note",
    study_list_courses: "checked your courses",
    study_get_changes_since: "checked recent changes",
    study_get_preferences: "checked your preferences",
    study_set_preferences: "updated your preferences",
    study_get_gmail_connection: "checked your Gmail connection",
    study_set_gmail_senders: "updated Gmail senders",
  };
  if (map[name]) return map[name];
  return name.replace(/^study_/, "").replace(/_/g, " ");
}

function shortSummary(
  trace: AgentTrace | null,
  frontendError?: FrontendErrorTrace | null,
): string {
  const serverErr = trace?.error;
  if (frontendError && trace)
    return `finished with a connection issue (${trace.steps.length} step${trace.steps.length === 1 ? "" : "s"})`;
  if (frontendError) return "could not reach the assistant";
  if (!trace) return "no details";
  if (serverErr)
    return `finished with an issue (${trace.steps.length} step${trace.steps.length === 1 ? "" : "s"})`;
  if (trace.steps.length === 0) return "answered directly";
  const calls = countToolCalls(trace);
  if (calls === 0) return "answered directly";
  return `used ${calls} tool${calls === 1 ? "" : "s"} in ${trace.steps.length} step${trace.steps.length === 1 ? "" : "s"}`;
}

const box: React.CSSProperties = {
  marginTop: 16,
  border: "1px solid #b3c4c0",
  borderRadius: 8,
  background: "#ffffff",
  fontSize: 14,
  lineHeight: 1.5,
  fontFamily: "Manrope, Arial, sans-serif",
  color: "#142e36",
};

const summaryRow: React.CSSProperties = {
  cursor: "pointer",
  padding: "10px 14px",
  fontWeight: 700,
  color: "#142e36",
  listStyle: "none",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
  fontFamily: "Manrope, Arial, sans-serif",
};

const section: React.CSSProperties = {
  borderTop: "1px solid #b3c4c0",
  padding: "10px 14px",
};

const pre: React.CSSProperties = {
  margin: "6px 0 0",
  padding: "8px 10px",
  background: "#142e36",
  color: "#f2f6f5",
  borderRadius: 6,
  fontSize: 13,
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
  fontWeight: 600,
  background: ok ? "rgba(10,102,94,.12)" : "rgba(150,53,44,.12)",
  color: ok ? "#0a665e" : "#96352c",
  marginLeft: 6,
});

const label: React.CSSProperties = {
  color: "#43585e",
  fontWeight: 600,
  fontSize: 13,
};

function tokenLabel(
  tokens:
    | { inputTokens: number; outputTokens: number; source: "api" | "estimated" }
    | null
    | undefined,
): string {
  if (!tokens) return "tokens n/a";
  const prefix = tokens.source === "api" ? "" : "~";
  return `${prefix}${formatNum(tokens.inputTokens)} in / ${prefix}${formatNum(tokens.outputTokens)} out`;
}

export function TempAgentTrace({
  trace,
  frontendError,
  durationMs,
}: TempAgentTraceProps) {
  const [devMode, setDevMode] = useState(false);
  const hasServerError = Boolean(trace?.error);
  const hasFrontendError = Boolean(frontendError);
  const ok = !hasServerError && !hasFrontendError;

  return (
    <details style={box} data-testid="temp-agent-trace">
      <summary style={summaryRow}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: 999,
              background: ok ? "#0a665e" : "#96352c",
            }}
          />
          agent trace — {shortSummary(trace, frontendError)}
        </span>
        <label
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 12,
            fontWeight: 600,
            fontSize: 13,
            color: "#43585e",
            cursor: "pointer",
            userSelect: "none",
          }}
          onClick={(e) => e.stopPropagation()}>
          <span
            style={{
              fontSize: 12,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            }}>
            Dev mode
          </span>
          <span
            style={{
              position: "relative",
              width: 34,
              height: 18,
              borderRadius: 999,
              background: devMode ? "#0a665e" : "#b3c4c0",
              transition: "background 120ms ease",
              flexShrink: 0,
            }}>
            <span
              style={{
                position: "absolute",
                top: 2,
                left: devMode ? 18 : 2,
                width: 14,
                height: 14,
                borderRadius: 999,
                background: "#ffffff",
                transition: "left 120ms ease",
              }}
            />
          </span>
          <input
            type="checkbox"
            checked={devMode}
            onChange={(e) => setDevMode(e.target.checked)}
            onClick={(e) => e.stopPropagation()}
            aria-label="Toggle dev mode"
            style={{
              position: "absolute",
              opacity: 0,
              width: 1,
              height: 1,
              pointerEvents: "none",
            }}
          />
        </label>
      </summary>

      {!devMode ? (
        // ---- friendly view ----
        <div style={section}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontWeight: 700,
              color: ok ? "#0a665e" : "#96352c",
              marginBottom: 6,
            }}>
            {ok ? "" : "Something went wrong"}
          </div>

          {trace && trace.steps.length > 0 ? (
            <div style={{ marginBottom: 8 }}>
              <div style={label}>What the assistant did</div>
              <ul style={{ margin: "4px 0 0 18px", padding: 0 }}>
                {trace.steps.map((step) => {
                  const tools = step.toolCalls.map((c) =>
                    friendlyToolName(c.name),
                  );
                  return (
                    <li key={step.round} style={{ marginBottom: 2 }}>
                      {tools.length === 0
                        ? `Step ${step.round}: prepared an answer`
                        : `Step ${step.round}: ${tools.join(", ")}`}
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : (
            <div style={{ marginBottom: 8, color: "#43585e" }}>
              The assistant answered without looking anything up.
            </div>
          )}

          {trace?.finalReply ? (
            <div style={{ marginBottom: 8 }}>
              <div style={label}>Final answer</div>
              <div style={{ color: "#1f3339" }}>
                {trace.finalReply.slice(0, 200)}
                {trace.finalReply.length > 200 ? "…" : ""}
              </div>
            </div>
          ) : null}

          {(hasServerError || hasFrontendError) && (
            <div style={{ marginBottom: 8 }}>
              <div style={label}>Issue</div>
              <div style={{ color: "#96352c" }}>
                {frontendError?.message ??
                  trace?.error?.message ??
                  "Unknown error"}
              </div>
            </div>
          )}

          {typeof durationMs === "number" && (
            <div style={{ color: "#43585e", fontSize: 12 }}>
              Finished in {(durationMs / 1000).toFixed(1)}s
            </div>
          )}
        </div>
      ) : (
        // ---- dev view (full details) ----
        <>
          <div style={section}>
            <div>
              <span style={label}>model: </span>
              <code>
                {trace?.model ?? "(none — bridge never reached the LLM)"}
              </code>
            </div>
            <div>
              <span style={label}>tokens (total): </span>
              {trace?.totalTokens ? (
                <>
                  <code>
                    {tokenLabel(trace.totalTokens)} ·{" "}
                    {formatNum(trace.totalTokens.totalTokens)} total
                  </code>
                  <span style={badge(trace.totalTokens.source === "api")}>
                    {trace.totalTokens.source === "api"
                      ? "exact (provider usage)"
                      : "~ estimated (no usage in response)"}
                  </span>
                </>
              ) : (
                "—"
              )}
            </div>
            <div>
              <span style={label}>mcp: </span>
              <code>{trace?.mcpServerUrl ?? "(unknown)"}</code>
            </div>
            <div>
              <span style={label}>
                tools discovered ({trace?.toolsDiscovered.length ?? 0}):{" "}
              </span>
              <code>
                {trace && trace.toolsDiscovered.length > 0
                  ? trace.toolsDiscovered.join(", ")
                  : "—"}
              </code>
            </div>
            {trace?.finalReply ? (
              <div style={{ marginTop: 4 }}>
                <span style={label}>final reply: </span>
                <span>
                  {trace.finalReply.slice(0, 160)}
                  {trace.finalReply.length > 160 ? "…" : ""}
                </span>
              </div>
            ) : null}
          </div>

          {trace && trace.steps.length > 0 ? (
            <div style={section}>
              <div style={label}>
                rounds ({trace.steps.length}) — open each to see thought → tools
                → outputs
              </div>
              {trace.steps.map((step) => (
                <details
                  key={step.round}
                  style={{
                    marginTop: 6,
                    border: "1px solid #b3c4c0",
                    borderRadius: 8,
                    background: "#fff",
                  }}>
                  <summary
                    style={{
                      cursor: "pointer",
                      padding: "6px 10px",
                      fontWeight: 700,
                    }}>
                    round {step.round}
                    <span style={badge(step.toolCalls.length === 0)}>
                      {step.toolCalls.length === 0
                        ? "no tool call"
                        : `${step.toolCalls.length} tool call${step.toolCalls.length === 1 ? "" : "s"}`}
                    </span>
                    {step.tokens && (
                      <span
                        style={{
                          color: "#43585e",
                          fontWeight: 400,
                          fontSize: 12,
                        }}>
                        {" "}
                        · {tokenLabel(step.tokens)}
                        {step.tokens.source === "estimated" ? " ~" : ""}
                      </span>
                    )}
                    {step.llmError && (
                      <span style={badge(false)}>llm error</span>
                    )}
                  </summary>
                  <div style={{ padding: "6px 10px 10px" }}>
                    {step.tokens && (
                      <details style={{ marginBottom: 6 }}>
                        <summary
                          style={{ cursor: "pointer", color: "#43585e" }}>
                          tokens:{" "}
                          <code>
                            {tokenLabel(step.tokens)} ·{" "}
                            {formatNum(step.tokens.totalTokens)} total
                          </code>
                          <span style={badge(step.tokens.source === "api")}>
                            {step.tokens.source === "api"
                              ? "exact"
                              : "~ estimated"}
                          </span>
                        </summary>
                        <div
                          style={{
                            fontSize: 12,
                            color: "#43585e",
                            marginTop: 4,
                          }}>
                          <div>
                            input (sent to model: messages + tool schemas):{" "}
                            <code>{formatNum(step.tokens.inputTokens)}</code>
                          </div>
                          <div>
                            output (model reply: content + tool calls):{" "}
                            <code>{formatNum(step.tokens.outputTokens)}</code>
                          </div>
                          {step.tokens.source === "api" && step.tokens.raw ? (
                            <pre style={pre}>
                              {JSON.stringify(step.tokens.raw, null, 2)}
                            </pre>
                          ) : (
                            <div>
                              source: provider omitted <code>usage</code> →
                              approx ~chars/4 of the request/response JSON.
                            </div>
                          )}
                        </div>
                      </details>
                    )}
                    <div style={label}>
                      ① LLM thought / draft (raw content)
                      {step.tokens && (
                        <span style={{ fontWeight: 400 }}>
                          {" "}
                          — output: {step.tokens.source === "api" ? "" : "~"}
                          {formatNum(step.tokens.outputTokens)} tokens
                          {step.tokens.source === "api"
                            ? " (exact)"
                            : " (est.)"}
                        </span>
                      )}
                    </div>
                    {step.llmThought ? (
                      <pre style={pre}>{step.llmThought}</pre>
                    ) : (
                      <p style={{ margin: "4px 0" }}>
                        — (empty: model said nothing before acting)
                      </p>
                    )}

                    <div style={{ ...label, marginTop: 8 }}>
                      ② tool calls (the model&apos;s decisions)
                    </div>
                    {step.toolCalls.length === 0 ? (
                      <p style={{ margin: "4px 0" }}>
                        — none this round (direct answer or small talk).
                      </p>
                    ) : (
                      step.toolCalls.map((call) => (
                        <details key={call.id} style={{ marginTop: 6 }}>
                          <summary style={{ cursor: "pointer" }}>
                            <code>{call.name}</code>{" "}
                            <span style={{ color: "#43585e" }}>
                              id={call.id}
                            </span>
                          </summary>
                          <div style={label}>arguments (parsed)</div>
                          <pre style={pre}>
                            {JSON.stringify(call.argumentsParsed, null, 2)}
                          </pre>
                          {call.argumentsRaw && (
                            <>
                              <div style={label}>arguments (raw string)</div>
                              <pre style={pre}>{call.argumentsRaw}</pre>
                            </>
                          )}
                        </details>
                      ))
                    )}

                    <div style={{ ...label, marginTop: 8 }}>
                      ③ tool outputs (what was fed back to the LLM)
                    </div>
                    {step.toolOutputs.length === 0 ? (
                      <p style={{ margin: "4px 0" }}>
                        — none (no tools ran this round).
                      </p>
                    ) : (
                      step.toolOutputs.map((out, i) => (
                        <details
                          key={`${out.tool}-${i}`}
                          style={{ marginTop: 6 }}
                          open={out.ok === false}>
                          <summary style={{ cursor: "pointer" }}>
                            <code>{out.tool}</code>
                            <span style={badge(out.ok)}>
                              {out.ok ? "ok" : "failed"}
                            </span>
                          </summary>
                          <pre style={pre}>
                            {out.renderedText || "— (empty output)"}
                          </pre>
                          {out.error && (
                            <>
                              <div style={label}>error envelope</div>
                              <pre style={pre}>
                                {JSON.stringify(out.error, null, 2)}
                              </pre>
                            </>
                          )}
                          {out.data && Object.keys(out.data).length > 0 && (
                            <>
                              <div style={label}>
                                raw data keys:{" "}
                                {Object.keys(out.data).join(", ")}
                              </div>
                              <pre style={pre}>
                                {JSON.stringify(out.data, null, 2).slice(
                                  0,
                                  3000,
                                )}
                              </pre>
                            </>
                          )}
                        </details>
                      ))
                    )}

                    {step.llmError && (
                      <>
                        <div style={{ ...label, marginTop: 8 }}>
                          round LLM error
                        </div>
                        <pre style={pre}>{step.llmError}</pre>
                      </>
                    )}
                  </div>
                </details>
              ))}
            </div>
          ) : (
            <div style={section}>
              <span style={label}>rounds: </span>— (no LLM rounds recorded; the
              failure happened before the loop)
            </div>
          )}

          <details style={section} open={hasServerError}>
            <summary style={{ cursor: "pointer", fontWeight: 700 }}>
              <span
                style={{
                  display: "inline-block",
                  width: 8,
                  height: 8,
                  borderRadius: 999,
                  background: hasServerError ? "#96352c" : "#0a665e",
                  marginRight: 6,
                }}
              />
              server error log (bridge / MCP / LLM)
            </summary>
            {trace?.error ? (
              <>
                <div>
                  <span style={label}>source: </span>
                  <code>{trace.error.source}</code>
                </div>
                <div>
                  <span style={label}>message: </span>
                  {trace.error.message}
                </div>
                {trace.error.detail && (
                  <pre style={pre}>{trace.error.detail}</pre>
                )}
              </>
            ) : (
              <p style={{ margin: "4px 0" }}>
                — none. The server loop finished without recording an error.
              </p>
            )}
          </details>

          <details style={section} open={hasFrontendError}>
            <summary style={{ cursor: "pointer", fontWeight: 700 }}>
              <span
                style={{
                  display: "inline-block",
                  width: 8,
                  height: 8,
                  borderRadius: 999,
                  background: hasFrontendError ? "#96352c" : "#0a665e",
                  marginRight: 6,
                }}
              />
              frontend / HTTP error log
            </summary>
            {frontendError ? (
              <>
                <div>
                  <span style={label}>source: </span>
                  <code>{frontendError.source}</code> (frontend = browser fetch
                  failed · bridge-http = /api/alexa-chat answered badly)
                </div>
                <div>
                  <span style={label}>message: </span>
                  {frontendError.message}
                </div>
                {typeof frontendError.status === "number" && (
                  <div>
                    <span style={label}>http status: </span>
                    <code>{frontendError.status}</code>
                  </div>
                )}
                {frontendError.detail && (
                  <pre style={pre}>{frontendError.detail}</pre>
                )}
                {frontendError.rawBody && (
                  <>
                    <div style={label}>raw bridge body</div>
                    <pre style={pre}>{frontendError.rawBody}</pre>
                  </>
                )}
              </>
            ) : (
              <p style={{ margin: "4px 0" }}>
                — none. The browser got a 200 with a non-empty reply.
              </p>
            )}
          </details>

          <details style={section}>
            <summary style={{ cursor: "pointer", fontWeight: 700 }}>
              raw trace JSON
            </summary>
            <pre style={pre}>{JSON.stringify(trace ?? null, null, 2)}</pre>
          </details>
        </>
      )}
    </details>
  );
}

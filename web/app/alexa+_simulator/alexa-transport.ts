export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
};

/**
 * The future MCP bridge endpoint. The Next.js route handler at
 * `app/api/alexa-chat/route.ts` will forward a conversation to the Python MCP
 * server; the browser never talks to the MCP server directly.
 */
export const ALEXA_BRIDGE_ENDPOINT = "/api/alexa-chat";

/**
 * Flip to `true` once the bridge route is implemented. While it is `false` the
 * simulator answers locally so the page can be exercised without a backend. The
 * bridge request below is already written so only this switch has to change.
 */
const BRIDGE_ENABLED = false;

const TYPING_MIN_MS = 700;
const TYPING_MAX_MS = 1400;

/**
 * Turns the conversation so far into Alexa+'s next reply.
 *
 * When the MCP bridge is connected this returns the backend's answer. Until
 * then it waits a moment and returns a scripted reply so the send, thinking,
 * and reply states can be tested end to end.
 */
export async function requestAlexaReply(messages: ChatMessage[]): Promise<string> {
  if (BRIDGE_ENABLED) {
    const bridgeReply = await requestFromBridge(messages);
    if (bridgeReply) return bridgeReply;
  }
  await wait(randomInt(TYPING_MIN_MS, TYPING_MAX_MS));
  return scriptedReply(messages);
}

/**
 * Posts the conversation to the bridge and returns its reply, or null when the
 * bridge is unavailable so the caller can fall back to the scripted answer.
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

/**
 * Scripted answers that stand in for the MCP tools Alexa+ will call later:
 * scheduling tasks, creating events, and reporting on the study plan.
 */
function scriptedReply(messages: ChatMessage[]): string {
  const lastUserMessage = [...messages].reverse().find((message) => message.role === "user");
  const text = lastUserMessage?.text.toLowerCase() ?? "";
  const mentions = (keywords: string[]) => keywords.some((keyword) => text.includes(keyword));

  if (/\b(hi|hello|hey)\b/.test(text) || mentions(["good morning", "good evening"])) {
    return "Hi! I can schedule study tasks, create events for deadlines, and tell you what is coming up. What would you like to do?";
  }
  if (mentions(["event", "calendar", "meeting", "appointment", "exam"])) {
    return "I can add that to your calendar. In the connected version I would call the MCP tool that creates an event and then confirm the time back to you. For now this is a scripted reply, so the event is not saved.";
  }
  if (mentions(["schedule", "plan", "study block", "block", "focus", "tomorrow"])) {
    return "I would place that as a study task on your plan, pick a duration from your usual workload, and check it against the rest of the day. This reply is simulated, so nothing has been scheduled yet.";
  }
  if (mentions(["due", "deadline", "assignment", "week", "today", "upcoming"])) {
    return "Once the MCP bridge is connected I would read your academic items and today's plan to answer that from real data. Right now I can only answer with this scripted message.";
  }
  if (mentions(["task", "remind", "reminder", "to-do", "todo"])) {
    return "I can turn that into a task and add it to your plan. This is a simulated response, so no task was created. Connect the MCP server to make it real.";
  }
  if (mentions(["thanks", "thank you"])) {
    return "Anytime. Ask me to schedule a task or create an event whenever you are ready.";
  }
  return "I can help with scheduling tasks, creating events, and answering questions about your plan. This is a scripted reply for now, ready to be replaced once the MCP bridge is connected.";
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

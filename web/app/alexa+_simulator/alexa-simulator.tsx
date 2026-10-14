"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { requestAlexaReply, type ChatMessage } from "./alexa-transport";

const WELCOME = "How can I help with your plan?";
const MAX_INPUT_HEIGHT = 160;

/** Ids only need to be unique within a session. */
let messageSeq = 0;
function nextMessageId(prefix: "user" | "assistant"): string {
  messageSeq += 1;
  return `${prefix}-${messageSeq}`;
}

export function AlexaSimulator() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const busyRef = useRef(false);

  const hasConversation = messages.length > 0;

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [messages, thinking]);

  /** Grow the textarea with its content, like the input on chat sites. */
  function resizeInput() {
    const input = inputRef.current;
    if (!input) return;
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, MAX_INPUT_HEIGHT)}px`;
  }

  async function send(rawText: string) {
    const text = rawText.trim();
    if (!text || busyRef.current) return;
    busyRef.current = true;

    const history: ChatMessage[] = [
      ...messages,
      { id: nextMessageId("user"), role: "user", text },
    ];
    setMessages(history);
    setDraft("");
    setError(null);
    setThinking(true);
    if (inputRef.current) inputRef.current.style.height = "auto";

    try {
      const reply = await requestAlexaReply(history);
      setMessages((current) => [
        ...current,
        { id: nextMessageId("assistant"), role: "assistant", text: reply },
      ]);
    } catch {
      setError("Alexa+ could not answer. Try again.");
    } finally {
      busyRef.current = false;
      setThinking(false);
      inputRef.current?.focus();
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send(draft);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(draft);
    }
  }

  const canSend = draft.trim().length > 0 && !thinking;

  return (
    <section
      className={hasConversation ? "chat" : "chat empty"}
      aria-label="Alexa+ conversation"
    >
      {hasConversation && (
        <div
          className="chat-log"
          role="log"
          aria-live="polite"
          aria-relevant="additions text"
          ref={logRef}
        >
          {messages.map((message) => (
            <article key={message.id} className={`chat-message ${message.role}`}>
              <p className="chat-bubble">{message.text}</p>
            </article>
          ))}

          {thinking && (
            <article className="chat-message assistant">
              <p className="chat-bubble chat-thinking">
                <span className="chat-dots" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
                <span className="sr-only">Alexa+ is thinking…</span>
              </p>
            </article>
          )}
        </div>
      )}

      <form className="chat-compose" onSubmit={submit}>
        {!hasConversation && <p className="chat-welcome">{WELCOME}</p>}
        {error && (
          <p className="chat-error" role="alert">
            {error}
          </p>
        )}
        <div className="chat-input-shell">
          <label className="sr-only" htmlFor="alexa-input">
            Message Alexa+
          </label>
          <textarea
            id="alexa-input"
            ref={inputRef}
            className="chat-input"
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              resizeInput();
            }}
            onKeyDown={handleKeyDown}
            placeholder="Message Alexa+…"
            rows={1}
            maxLength={1000}
            disabled={thinking}
          />
          <button
            className="chat-send"
            type="submit"
            disabled={!canSend}
            aria-label="Send message"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M12 19V5" />
              <path d="m5 12 7-7 7 7" />
            </svg>
          </button>
        </div>
      </form>
    </section>
  );
}

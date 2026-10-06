"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

type Connection = {
  connection_id: string | null;
  account_email: string | null;
  allowed_senders: string[];
  status: "not_configured" | "not_connected" | "connected";
  oauth_configured: boolean;
};

export default function GmailPage() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [senders, setSenders] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/gmail-connection", { cache: "no-store" })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not load Gmail settings.");
        setConnection(data);
        setSenders(data.allowed_senders.join("\n"));
        const result = new URLSearchParams(window.location.search).get("connection");
        if (result === "connected") setMessage("Gmail connected. Your sender list is ready for the first import.");
        else if (result) setError(result === "denied"
          ? "Google access was declined. You can try connecting again."
          : "Gmail could not be connected. Check the backend setup and try again.");
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Could not load Gmail settings."))
      .finally(() => setLoading(false));
  }, []);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    const allowed_senders = senders.split(/[\n,]/).map((sender) => sender.trim()).filter(Boolean);
    if (allowed_senders.length < 1 || allowed_senders.length > 50) {
      setError("Enter between 1 and 50 sender email addresses.");
      return;
    }
    setSaving(true);
    try {
      const response = await fetch("/api/gmail-connection", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ allowed_senders }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not save sender addresses.");
      setConnection(data);
      setSenders(data.allowed_senders.join("\n"));
      setMessage("Allowed senders saved. Connect Gmail when you are ready.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save sender addresses.");
    } finally {
      setSaving(false);
    }
  }

  const configured = Boolean(connection?.connection_id && connection.allowed_senders.length);
  const hasUnsavedChanges = connection !== null && senders.trim() !== connection.allowed_senders.join("\n");

  return (
    <main className="page-shell">
      <div className="entry-page gmail-page">
        <nav className="page-nav"><Link href="/">← Add a source</Link></nav>
        <header className="page-header">
          <h1>Connect Gmail</h1>
          <p>Choose the senders Acadra may import from. Your Google sign-in stays with Google; Acadra never asks for your Gmail password.</p>
        </header>

        <section className="gmail-status" aria-label="Connection status">
          <div>
            <h2>Connection</h2>
            <p>{loading ? "Loading settings…" : connection?.status === "connected"
              ? `Connected as ${connection.account_email}`
              : "No Gmail account connected yet."}</p>
          </div>
          <span className={connection?.status === "connected" ? "status-pill connected" : "status-pill"}>
            {connection?.status === "connected" ? "Connected" : "Not connected"}
          </span>
        </section>

        <form className="entry-form gmail-form" onSubmit={save}>
          <div className="field">
            <label htmlFor="gmail-senders">Allowed sender email addresses</label>
            <textarea
              id="gmail-senders"
              value={senders}
              onChange={(event) => setSenders(event.target.value)}
              placeholder={"professor@university.edu\nannouncements@university.edu"}
              rows={6}
              spellCheck={false}
              disabled={loading || saving}
              aria-describedby="gmail-senders-hint"
            />
            <p className="field-hint" id="gmail-senders-hint">One exact address per line, up to 50. Save this list before connecting. Messages from other senders will be skipped when import is added.</p>
          </div>

          {error && <p className="message error" role="alert">{error}</p>}
          {message && <p className="message success" role="status">{message}</p>}

          <div className="gmail-actions">
            <button className="submit-button" type="submit" disabled={loading || saving}>
              {saving ? "Saving…" : "Save allowed senders"}
            </button>
            <a
              className={`connect-button${!configured || hasUnsavedChanges || !connection?.oauth_configured ? " disabled" : ""}`}
              href={configured && !hasUnsavedChanges && connection?.oauth_configured ? "/api/gmail-connection/connect" : undefined}
              aria-disabled={!configured || hasUnsavedChanges || !connection?.oauth_configured}
              onClick={(event) => {
                if (!configured || hasUnsavedChanges || !connection?.oauth_configured) event.preventDefault();
              }}
            >{connection?.status === "connected" ? "Reconnect Google" : "Continue with Google"}</a>
          </div>
          {!loading && !connection?.oauth_configured && (
            <p className="field-hint">Google OAuth client settings are missing on the backend.</p>
          )}
        </form>

        <p className="gmail-privacy">Google will ask for Gmail read-only access to the account. The sender list limits what Acadra processes; it does not narrow Google’s permission. This setup does not fetch messages yet.</p>
      </div>
    </main>
  );
}

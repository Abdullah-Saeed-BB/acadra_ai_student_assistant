"use client";

import { FormEvent, useRef, useState } from "react";

type EntryMode = "text" | "file";
type SaveResult = {
  source_document_id: string;
  revision_no: number;
  processing_status: string;
  academic_item_ids: string[];
  review_count: number;
};

type PendingSource = {
  id: string;
  mode: EntryMode;
  title: string;
  text?: string;
  file?: File;
};

type ProcessingResult = {
  id: string;
  title: string;
  ok: boolean;
  extractionFailed: boolean;
  message: string;
};

const MAX_TEXT_BYTES = 64 * 1024;
const MAX_HTML_BYTES = 256 * 1024;
const MAX_PDF_BYTES = 5 * 1024 * 1024;

function fileError(file: File): string | null {
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (extension !== "html" && extension !== "htm" && extension !== "pdf") {
    return "Choose an HTML (.html or .htm) or PDF (.pdf) file.";
  }
  if (file.size === 0) return "The selected file is empty.";
  const limit = extension === "pdf" ? MAX_PDF_BYTES : MAX_HTML_BYTES;
  if (file.size > limit) {
    return extension === "pdf"
      ? "PDF files must be 5 MiB or smaller."
      : "HTML files must be 256 KiB or smaller.";
  }
  return null;
}

function sourceLabel(source: PendingSource): string {
  if (source.title) return source.title;
  if (source.mode === "file" && source.file) return source.file.name;
  return "Pasted text";
}

export function SourceEntryForm() {
  const [mode, setMode] = useState<EntryMode>("text");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingSource[]>([]);
  const [results, setResults] = useState<ProcessingResult[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);

  function changeMode(next: EntryMode) {
    setMode(next);
    setError(null);
  }

  function addSource() {
    setError(null);

    const cleanTitle = title.trim();
    if (title && !cleanTitle) {
      setError("Enter a title or leave the title field empty.");
      return;
    }
    if (mode === "text") {
      if (!text.trim()) {
        setError("Paste or type some text before adding.");
        return;
      }
      if (new TextEncoder().encode(text).length > MAX_TEXT_BYTES) {
        setError("Text must be 64 KiB or smaller.");
        return;
      }
    } else {
      if (!file) {
        setError("Choose a file before adding.");
        return;
      }
      const validation = fileError(file);
      if (validation) {
        setError(validation);
        return;
      }
    }

    const source: PendingSource = {
      id: (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random())),
      mode,
      title: cleanTitle,
      text: mode === "text" ? text : undefined,
      file: mode === "file" ? file! : undefined,
    };
    setPending((prev) => [...prev, source]);
    setTitle("");
    setText("");
    setFile(null);
    if (fileInput.current) fileInput.current.value = "";
  }

  function removeSource(id: string) {
    setPending((prev) => prev.filter((source) => source.id !== id));
  }

  async function submitSource(source: PendingSource): Promise<ProcessingResult> {
    const label = sourceLabel(source);
    try {
      const options: RequestInit = { method: "POST" };
      if (source.mode === "text") {
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify({
          text: source.text,
          ...(source.title && { title: source.title }),
        });
      } else {
        const body = new FormData();
        body.append("file", source.file!);
        if (source.title) body.append("title", source.title);
        options.body = body;
      }

      const response = await fetch("/api/manual-entry", options);
      const data: SaveResult & { error?: string; details?: { message: string }[] } =
        await response.json();
      if (!response.ok) {
        throw new Error(data.details?.[0]?.message || data.error || "The source could not be saved.");
      }
      return {
        id: source.id,
        title: label,
        ok: true,
        extractionFailed: data.processing_status === "failed",
        message: `Revision ${data.revision_no} - ${data.academic_item_ids.length} academic ${data.academic_item_ids.length === 1 ? "item" : "items"} found - ${data.review_count} to review${data.processing_status === "pending_configuration" ? " (automatic extraction not configured)" : data.processing_status === "failed" ? " (extraction failed)" : ""}`,
      };
    } catch (cause) {
      return {
        id: source.id,
        title: label,
        ok: false,
        extractionFailed: false,
        message: cause instanceof Error ? cause.message : "The source could not be saved. Try again.",
      };
    }
  }

  async function startProcessing(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (busy || pending.length === 0) return;

    setBusy(true);
    setError(null);
    setResults([]);
    const batch = pending;
    setPending([]);

    const collected: ProcessingResult[] = [];
    for (const source of batch) {
      const result = await submitSource(source);
      collected.push(result);
      setResults([...collected]);
    }
    setBusy(false);
  }

  const failedResults = results.filter((item) => !item.ok || item.extractionFailed);

  return (
    <form className="entry-form" onSubmit={startProcessing}>
      <fieldset className="source-choice" disabled={busy}>
        <legend>Source type</legend>
        <div className="choice-row">
          <label className={mode === "text" ? "choice active" : "choice"}>
            <input type="radio" name="source-type" value="text" checked={mode === "text"} onChange={() => changeMode("text")} disabled={busy} />
            Text
          </label>
          <label className={mode === "file" ? "choice active" : "choice"}>
            <input type="radio" name="source-type" value="file" checked={mode === "file"} onChange={() => changeMode("file")} disabled={busy} />
            HTML or PDF file
          </label>
        </div>
      </fieldset>

      <div className="field">
        <label htmlFor="source-title">Title <span className="optional">optional</span></label>
        <input id="source-title" type="text" value={title} maxLength={200} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. Course announcement" disabled={busy} />
        <p className="field-hint">Files use their filename when no title is entered.</p>
      </div>

      {mode === "text" ? (
        <div className="field">
          <label htmlFor="source-text">Text</label>
          <textarea id="source-text" value={text} onChange={(event) => setText(event.target.value)} placeholder="Paste an announcement, assignment, or course note here..." rows={11} disabled={busy} />
          <p className="field-hint">Up to 64 KiB of text.</p>
        </div>
      ) : (
        <div className="field">
          <label htmlFor="source-file">File</label>
          <input id="source-file" ref={fileInput} type="file" accept=".html,.htm,.pdf,text/html,application/pdf" onChange={(event) => { setFile(event.target.files?.[0] ?? null); setError(null); }} disabled={busy} />
          <p className="field-hint">HTML: up to 256 KiB. PDF: up to 5 MiB and 20 pages. Scanned PDFs need OCR and cannot be processed yet.</p>
        </div>
      )}

      {error && <p className="message error" role="alert">{error}</p>}

      <div className="choice-row" style={{ marginBottom: 22 }}>
        <button type="button" className="submit-button" onClick={addSource} disabled={busy}>
          Add
        </button>
      </div>

      {pending.length > 0 && (
        <div className="message" role="status" style={{ background: "rgba(12,119,109,0.05)", border: "1px solid var(--line)" }}>
          <strong>{pending.length} source{pending.length === 1 ? "" : "s"} ready to process</strong>
          <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
            {pending.map((source) => (
              <li key={source.id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span>{sourceLabel(source)} <span style={{ color: "var(--muted)" }}>({source.mode === "file" ? "file" : "text"})</span></span>
                <button type="button" aria-label="Remove source" onClick={() => removeSource(source.id)} disabled={busy} style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--priority-coral)", cursor: "pointer", fontWeight: 700, fontSize: 18, lineHeight: 1 }}>
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {results.length > 0 && (
        <div
          className={`message ${failedResults.length === results.length ? "error" : "success"}`}
          role="status"
        >
          <strong>Processing results</strong>
          <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
            {results.map((item) => (
              <li
                key={item.id}
                style={!item.ok || item.extractionFailed ? { color: "var(--priority-coral)" } : undefined}
              >
                <strong>{item.title}:</strong> {item.ok ? "saved" : "failed"} - {item.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      <button className="submit-button" type="submit" disabled={busy || pending.length === 0}>
        {busy ? "Processing..." : "Start Processing"}
      </button>
    </form>
  );
}



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

export default function Home() {
  const [mode, setMode] = useState<EntryMode>("text");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SaveResult | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  function changeMode(next: EntryMode) {
    setMode(next);
    setError(null);
    setResult(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);

    const cleanTitle = title.trim();
    if (title && !cleanTitle) {
      setError("Enter a title or leave the title field empty.");
      return;
    }
    if (mode === "text") {
      if (!text.trim()) {
        setError("Paste or type some text before saving.");
        return;
      }
      if (new TextEncoder().encode(text).length > MAX_TEXT_BYTES) {
        setError("Text must be 64 KiB or smaller.");
        return;
      }
    } else {
      if (!file) {
        setError("Choose a file before saving.");
        return;
      }
      const validation = fileError(file);
      if (validation) {
        setError(validation);
        return;
      }
    }

    setBusy(true);
    try {
      const options: RequestInit = { method: "POST" };
      if (mode === "text") {
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify({ text, ...(cleanTitle && { title: cleanTitle }) });
      } else {
        const body = new FormData();
        body.append("file", file!);
        if (cleanTitle) body.append("title", cleanTitle);
        options.body = body;
      }

      const response = await fetch("/api/manual-entry", options);
      const data: SaveResult & { error?: string; details?: { message: string }[] } =
        await response.json();
      if (!response.ok) {
        throw new Error(data.details?.[0]?.message || data.error || "The source could not be saved.");
      }
      setResult(data);
      setTitle("");
      setText("");
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The source could not be saved. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page-shell">
      <div className="entry-page">
        <header className="page-header">
          <h1>Add a source</h1>
          <p>Enter information for your study workspace. Paste text or upload an HTML or PDF file.</p>
        </header>

        <form className="entry-form" onSubmit={submit}>
          <fieldset className="source-choice" disabled={busy}>
            <legend>Source type</legend>
            <div className="choice-row">
              <label className={mode === "text" ? "choice active" : "choice"}>
                <input type="radio" name="source-type" value="text" checked={mode === "text"} onChange={() => changeMode("text")} />
                Text
              </label>
              <label className={mode === "file" ? "choice active" : "choice"}>
                <input type="radio" name="source-type" value="file" checked={mode === "file"} onChange={() => changeMode("file")} />
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
              <textarea id="source-text" value={text} onChange={(event) => setText(event.target.value)} placeholder="Paste an announcement, assignment, or course note here…" rows={11} disabled={busy} />
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
          {result && (
            <div className="message success" role="status">
              <strong>Source saved.</strong>
              <span>Revision {result.revision_no} · {result.academic_item_ids.length} academic {result.academic_item_ids.length === 1 ? "item" : "items"} found · {result.review_count} to review</span>
              {result.processing_status === "pending_configuration" && <span>Automatic extraction is not configured yet.</span>}
              {result.processing_status === "failed" && <span>Automatic extraction failed. The source was still saved.</span>}
            </div>
          )}

          <button className="submit-button" type="submit" disabled={busy}>
            {busy ? "Saving source…" : "Save source"}
          </button>
        </form>
      </div>
    </main>
  );
}

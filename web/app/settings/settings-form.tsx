"use client";

import { FormEvent, useEffect, useState } from "react";

type Preferences = {
  preferred_daily_minutes: number | null;
  focus_task_count: number | null;
  updated_at: string | null;
};

export function SettingsForm() {
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [minutes, setMinutes] = useState("");
  const [focusCount, setFocusCount] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/preferences", { cache: "no-store" })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not load planning preferences.");
        setPreferences(data);
        setMinutes(data.preferred_daily_minutes == null ? "" : String(data.preferred_daily_minutes));
        setFocusCount(data.focus_task_count == null ? "" : String(data.focus_task_count));
      })
      .catch((cause) =>
        setError(cause instanceof Error ? cause.message : "Could not load planning preferences."),
      )
      .finally(() => setLoading(false));
  }, []);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    const preferred_daily_minutes =
      minutes.trim() === "" ? null : Number(minutes);
    const focus_task_count =
      focusCount.trim() === "" ? null : Number(focusCount);
    const clear_preferred_daily_minutes = minutes.trim() === "";
    const clear_focus_task_count = focusCount.trim() === "";

    if (preferred_daily_minutes !== null && (!Number.isInteger(preferred_daily_minutes) || preferred_daily_minutes < 1 || preferred_daily_minutes > 1440)) {
      setError("Preferred daily workload must be between 1 and 1440 minutes.");
      return;
    }
    if (focus_task_count !== null && (!Number.isInteger(focus_task_count) || focus_task_count < 1 || focus_task_count > 20)) {
      setError("Focus task count must be between 1 and 20.");
      return;
    }

    setSaving(true);
    try {
      const response = await fetch("/api/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
        preferred_daily_minutes,
        focus_task_count,
        clear_preferred_daily_minutes,
        clear_focus_task_count,
      }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not save planning preferences.");
      setPreferences(data);
      setMinutes(data.preferred_daily_minutes == null ? "" : String(data.preferred_daily_minutes));
      setFocusCount(data.focus_task_count == null ? "" : String(data.focus_task_count));
      setMessage("Planning preferences saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save planning preferences.");
    } finally {
      setSaving(false);
    }
  }

  const hasUnsavedChanges =
    preferences !== null &&
    (minutes.trim() !== (preferences.preferred_daily_minutes == null ? "" : String(preferences.preferred_daily_minutes)) ||
      focusCount.trim() !== (preferences.focus_task_count == null ? "" : String(preferences.focus_task_count)));

  return (
    <form className="entry-form" onSubmit={save}>
      <div className="field">
        <label htmlFor="preferred-daily-minutes">Preferred daily workload (minutes)</label>
        <input
          id="preferred-daily-minutes"
          type="number"
          min={1}
          max={1440}
          step={1}
          value={minutes}
          onChange={(event) => setMinutes(event.target.value)}
          placeholder="e.g. 120"
          disabled={loading || saving}
        />
        <p className="field-hint">Total study minutes you usually want to plan for a day.</p>
      </div>

      <div className="field">
        <label htmlFor="focus-task-count">Usual number of focus tasks</label>
        <input
          id="focus-task-count"
          type="number"
          min={1}
          max={20}
          step={1}
          value={focusCount}
          onChange={(event) => setFocusCount(event.target.value)}
          placeholder="e.g. 3"
          disabled={loading || saving}
        />
        <p className="field-hint">How many tasks you usually want to focus on in a day.</p>
      </div>

      {error && <p className="message error" role="alert">{error}</p>}
      {message && <p className="message success" role="status">{message}</p>}

      <div className="page-actions">
        <button className="submit-button" type="submit" disabled={loading || saving || !hasUnsavedChanges}>
          {saving ? "Saving…" : "Save preferences"}
        </button>
      </div>
    </form>
  );
}
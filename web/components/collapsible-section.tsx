"use client";

import type { ReactNode } from "react";
import { useState } from "react";

/**
 * A panel section whose body can be shown or hidden with a toggle button.
 * Keeps the heading and aria-labelledby id so the section stays labelled.
 */
export function CollapsibleSection({
  id,
  title,
  empty = false,
  defaultOpen = true,
  children,
}: {
  id: string;
  title: string;
  empty?: boolean;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const contentId = `${id}-content`;

  return (
    <section className={"panel " + (empty ? "empty" : "")} aria-labelledby={id}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}>
        <h2 id={id} style={{ margin: 0 }}>
          {title}
        </h2>
        <button
          type="button"
          className="connect-button-small"
          aria-expanded={open}
          aria-controls={contentId}
          aria-label={open ? "Hide content" : "Show content"}
          onClick={() => setOpen((value) => !value)}>
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            width="18"
            height="18"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round">
            {open ? <path d="m6 15 6-6 6 6" /> : <path d="m6 9 6 6 6-6" />}
          </svg>
        </button>
      </div>
      {open ? (
        <div id={contentId} style={{ marginTop: 12 }}>
          {children}
        </div>
      ) : null}
    </section>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";

type Connection = {
  status: "not_configured" | "not_connected" | "connected";
};

export default function ConnectorsPage() {
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    fetch("/api/gmail-connection", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const data: Connection = await response.json();
        setConnected(data.status === "connected");
      })
      .catch(() => setConnected(false));
  }, []);

  return (
    <div className="page">
      <PageHeader
        title="Connectors"
        description="Connect external sources so Acadra can pull in academic items and tasks."
      />

      <section className="connectors-grid" aria-label="Available connectors">
        <Link href="/connecter/gmail" className="connector-card">
          <div className="connector-card-head">
            <div className="connector-card-title-wrap">
              <svg
                className="connector-card-icon"
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true">
                <rect x="3" y="5" width="18" height="14" rx="2.5" />
                <path d="m4 7 8 6 8-6" />
              </svg>
              <h2 className="connector-card-title">Gmail</h2>
            </div>
            <span
              className={
                connected
                  ? "connector-card-status connector-card-status--connected"
                  : "connector-card-status"
              }>
              {connected ? "Connected" : "Available"}
            </span>
          </div>
          <p className="connector-card-description">
            Save the exact sender addresses Acadra may import from and start Google OAuth. Message import is not yet implemented.
          </p>
        </Link>
      </section>
    </div>
  );
}

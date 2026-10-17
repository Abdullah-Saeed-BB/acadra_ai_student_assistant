import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = {
  title: "Connectors",
};

const connectors = [
  {
    href: "/connecters/gmail",
    name: "Gmail",
    description:
      "Save the exact sender addresses Acadra may import from and start Google OAuth. Message import is not yet implemented.",
    status: "Available",
  },
];

export default function ConnectorsPage() {
  return (
    <div className="page">
      <PageHeader
        title="Connectors"
        description="Connect external sources so Acadra can pull in academic items and tasks."
      />

      <section className="connectors-grid" aria-label="Available connectors">
        {connectors.map((connector) => (
          <Link
            key={connector.href}
            href={connector.href}
            className="connector-card"
          >
            <div className="connector-card-head">
              <h2 className="connector-card-title">{connector.name}</h2>
              <span className="connector-card-status">{connector.status}</span>
            </div>
            <p className="connector-card-description">{connector.description}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}

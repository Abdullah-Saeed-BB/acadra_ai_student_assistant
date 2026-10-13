import type { Metadata } from "next";
import Link from "next/link";
import { SourceEntryForm } from "./source-entry-form";

export const metadata: Metadata = {
  title: "Add source",
};

export default function AddSourcePage() {
  return (
    <div className="page">
      <header className="page-header">
        <p className="eyebrow">Add source</p>
        <h1 className="page-title">Add a source</h1>
        <p className="page-lede">
          Enter information for your study workspace. Paste text or upload an HTML or PDF
          file.
        </p>
        <div className="page-actions">
          <Link href="/gmail">Set up Gmail</Link>
        </div>
      </header>

      <SourceEntryForm />
    </div>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import { SourceEntryForm } from "./source-entry-form";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = {
  title: "Add source",
};

export default function AddSourcePage() {
  return (
    <div className="page">
      <PageHeader
        title="Add a source"
        description="Enter information for your study workspace. Paste text or upload an HTML or PDF file."
      >
        <div className="page-actions">
          <Link href="/gmail">Set up Gmail</Link>
        </div>
      </PageHeader>

      <SourceEntryForm />
    </div>
  );
}

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
        description="Paste text or upload an HTML or PDF file of your study workspace."
        tooltip="Why? Your study workspace (announcements, assignments, course notes) is turned into structured academic items (tasks, deadlines, events). After processing, the source is saved as a revision, academic items are extracted for review, and you can approve or edit them before they become tasks."
      />

      <SourceEntryForm />
    </div>
  );
}

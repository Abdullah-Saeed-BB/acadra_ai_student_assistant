import type { Metadata } from "next";
import { PlannedView } from "@/components/planned-view";

export const metadata: Metadata = {
  title: "Source",
};

export default async function SourceDetailPage({
  params,
}: {
  params: Promise<{ source_document_id: string }>;
}) {
  const { source_document_id } = await params;
  return (
    <PlannedView
      title="Source"
      description="A single source's revisions, extracted candidates (including those held back for review), and change history, with links to the academic items it produced."
      note={`Source ${source_document_id}`}
    />
  );
}

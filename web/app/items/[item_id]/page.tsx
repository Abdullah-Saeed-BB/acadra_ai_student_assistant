import type { Metadata } from "next";
import { PlannedView } from "@/components/planned-view";

export const metadata: Metadata = {
  title: "Academic item",
};

export default async function AcademicItemPage({
  params,
}: {
  params: Promise<{ item_id: string }>;
}) {
  const { item_id } = await params;
  return (
    <PlannedView
      title="Academic item"
      description="One extracted academic record: type, course, due date, and review state, together with the source excerpts and evidence that produced it."
      note={`Item ${item_id}`}
    />
  );
}

import type { Metadata } from "next";
import { PlannedView } from "@/components/planned-view";

export const metadata: Metadata = {
  title: "Task detail",
};

export default async function TaskDetailPage({
  params,
}: {
  params: Promise<{ task_id: string }>;
}) {
  const { task_id } = await params;
  return (
    <PlannedView
      title="Task detail"
      description="One task with its steps, progress, and optional academic-item or course link. Change the estimated effort, move the task to another day, reorder it, or split it into steps."
      note={`Task ${task_id}`}
    />
  );
}

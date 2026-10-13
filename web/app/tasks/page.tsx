import type { Metadata } from "next";
import { PlannedView } from "@/components/planned-view";

export const metadata: Metadata = {
  title: "All tasks",
};

export default function TasksPage() {
  return (
    <PlannedView
      title="All tasks"
      description="Every task, with filters for status, course, academic item, and tag."
    />
  );
}

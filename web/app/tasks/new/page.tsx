import type { Metadata } from "next";
import { PlannedView } from "@/components/planned-view";

export const metadata: Metadata = {
  title: "New task",
};

export default function NewTaskPage() {
  return (
    <PlannedView
      title="New task"
      description="Create a student task, optionally linked to an academic item, a course, or a parent task, with a title, an optional selected day, and an effort estimate."
    />
  );
}

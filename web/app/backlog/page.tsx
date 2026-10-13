import type { Metadata } from "next";
import { PlannedView } from "@/components/planned-view";

export const metadata: Metadata = {
  title: "Backlog",
};

export default function BacklogPage() {
  return (
    <PlannedView
      title="Backlog"
      description="Unfinished tasks that have no selected day. Review the remaining effort, choose a day for a task, or split it into smaller steps."
    />
  );
}

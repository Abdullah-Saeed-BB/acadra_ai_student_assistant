import type { Metadata } from "next";
import { PlannedView } from "@/components/planned-view";

export const metadata: Metadata = {
  title: "Upcoming",
};

export default function UpcomingPage() {
  return (
    <PlannedView
      title="Upcoming"
      description="Tasks selected for the next days, grouped by day, so you can rebalance upcoming work. Moving a task changes only its selected day."
    />
  );
}

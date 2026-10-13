import type { Metadata } from "next";
import { PlannedView } from "@/components/planned-view";

export const metadata: Metadata = {
  title: "Settings",
};

export default function SettingsPage() {
  return (
    <PlannedView
      title="Settings"
      description="Planning preferences used for daily suggestions: your preferred daily workload and the usual number of focus tasks."
    />
  );
}

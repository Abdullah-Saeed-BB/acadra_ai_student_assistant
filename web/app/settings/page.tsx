import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";
import { SettingsForm } from "./settings-form";

export const metadata: Metadata = {
  title: "Settings",
};

export default function SettingsPage() {
  return (
    <div className="page">
      <PageHeader
        title="Settings"
        description="Planning preferences used for daily suggestions: your preferred daily workload and the usual number of focus tasks."
      />
      <SettingsForm />
    </div>
  );
}
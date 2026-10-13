import type { Metadata } from "next";
import { PlannedView } from "@/components/planned-view";

export const metadata: Metadata = {
  title: "Alexa+ simulator",
};

export default function AlexaSimulatorPage() {
  return (
    <PlannedView
      title="Alexa+ simulator"
      description="A chat page for testing MCP connections where the bot acts as Alexa+: scheduling tasks, creating events, and answering questions about your plan."
    />
  );
}

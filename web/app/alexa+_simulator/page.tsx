import type { Metadata } from "next";
import { AlexaSimulator } from "./alexa-simulator";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = {
  title: "Alexa+ simulator",
};

export default function AlexaSimulatorPage() {
  return (
    <div className="page page-chat">
      <PageHeader title="Alexa+ simulator" />

      <AlexaSimulator />
    </div>
  );
}

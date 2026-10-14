import type { Metadata } from "next";
import { AlexaSimulator } from "./alexa-simulator";

export const metadata: Metadata = {
  title: "Alexa+ simulator",
};

export default function AlexaSimulatorPage() {
  return (
    <div className="page page-chat">
      <header className="page-header">
        <h1 className="page-title display-accent">Alexa+ simulator</h1>
      </header>

      <AlexaSimulator />
    </div>
  );
}

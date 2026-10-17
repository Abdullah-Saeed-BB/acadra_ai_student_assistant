import type { Metadata } from "next";
import Link from "next/link";
import { GmailConnectionForm } from "./gmail-connection-form";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = {
  title: "Gmail connection",
};

export default function GmailPage() {
  return (
    <div className="page">
      <PageHeader
        title="Connect Gmail"
        description="Choose which senders Acadra can import from. Google handles sign-in."
      />

      <GmailConnectionForm />
    </div>
  );
}

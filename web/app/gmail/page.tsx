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
      <nav className="page-nav"><Link href="/sources/new">← Add a source</Link></nav>
      <PageHeader
        title="Connect Gmail"
        description="Choose the senders Acadra may import from. Your Google sign-in stays with Google; Acadra never asks for your Gmail password."
      />

      <GmailConnectionForm />
    </div>
  );
}

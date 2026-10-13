import type { Metadata } from "next";
import Link from "next/link";
import { GmailConnectionForm } from "./gmail-connection-form";

export const metadata: Metadata = {
  title: "Gmail connection",
};

export default function GmailPage() {
  return (
    <div className="page">
      <nav className="page-nav"><Link href="/sources/new">← Add a source</Link></nav>
      <header className="page-header">
        <p className="eyebrow">Gmail</p>
        <h1 className="page-title">Connect Gmail</h1>
        <p className="page-lede">Choose the senders Acadra may import from. Your Google sign-in stays with Google; Acadra never asks for your Gmail password.</p>
      </header>

      <GmailConnectionForm />
    </div>
  );
}

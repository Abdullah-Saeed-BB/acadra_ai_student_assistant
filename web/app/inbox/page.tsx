import type { Metadata } from "next";
import { PlannedView } from "@/components/planned-view";

export const metadata: Metadata = {
  title: "Inbox",
};

export default function InboxPage() {
  return (
    <PlannedView
      title="Inbox"
      description="Recent source revisions and change events, ordered so you can see what changed, why it matters, and which record it affects before turning it into a task."
    />
  );
}

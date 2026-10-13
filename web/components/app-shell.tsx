import type { ReactNode } from "react";
import { Sidebar } from "@/components/sidebar";

/**
 * The workspace frame: a persistent sidebar beside the page content. Layouts
 * stay mounted across navigation, so the sidebar keeps its state and scroll.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-frame">
      <Sidebar />
      <main className="app-content">{children}</main>
    </div>
  );
}

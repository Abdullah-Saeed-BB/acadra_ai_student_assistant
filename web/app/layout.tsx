import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Acadra study workspace",
  description: "Add academic sources and configure your study workspace.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

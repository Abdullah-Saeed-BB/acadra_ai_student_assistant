import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Add a source",
  description: "Enter text or upload an HTML or PDF source for your study workspace.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Page not found",
};

export default function NotFound() {
  return (
    <div className="not-found">
      <h1 className="display-accent">Page not found</h1>
      <p>
        The page you are looking for does not exist or may have moved. Head back
        to Today to pick up where you left off.
      </p>
      <Link className="submit-button" href="/">
        Back to Today
      </Link>
    </div>
  );
}

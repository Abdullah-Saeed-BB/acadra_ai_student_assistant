import Link from "next/link";
import { PageHeader } from "@/components/page-header";

export default function TaskNotFound() {
  return (
    <div className="page">
      <PageHeader
        title="Task not found"
        description="This task does not exist or was removed. Your lists are unchanged."
      />
      <section className="panel">
        <div className="page-actions">
          <Link className="connect-button" href="/tasks">
            All tasks
          </Link>
          <Link className="page-link" href="/">
            Back to Today
          </Link>
        </div>
      </section>
    </div>
  );
}

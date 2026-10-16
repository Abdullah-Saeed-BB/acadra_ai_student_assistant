import Link from "next/link";
import { PageHeader } from "@/components/page-header";

export default function AcademicItemNotFound() {
  return (
    <div className="page">
      <PageHeader
        title="Academic item not found"
        description="This record does not exist or was removed. Your courses are unchanged."
      />
      <section className="panel">
        <div className="page-actions">
          <Link className="connect-button" href="/courses">
            Courses
          </Link>
          <Link className="page-link" href="/inbox">
            Inbox
          </Link>
        </div>
      </section>
    </div>
  );
}

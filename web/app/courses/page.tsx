import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { CourseBoard } from "@/components/course-board";
import { CourseCreateButton } from "@/components/academic-dialogs";
import {
  backendUnavailableMessage,
  listAcademicItems,
  listCourses,
} from "@/lib/academics";

export const metadata: Metadata = {
  title: "Courses",
};

export default async function CoursesPage() {
  let courses = null;
  let items = null;
  let error: string | null = null;
  try {
    const [coursePage, itemPage] = await Promise.all([
      listCourses("limit=100"),
      listAcademicItems("limit=100"),
    ]);
    courses = coursePage.items;
    items = itemPage.items;
  } catch (cause) {
    error =
      cause instanceof Error ? cause.message : backendUnavailableMessage();
  }

  return (
    <div className="page">
      <PageHeader
        title="Courses"
        description="Your courses with the academic items.">
        <CourseCreateButton />
      </PageHeader>

      {error ? (
        <section className="panel">
          <p className="message error" role="alert">
            {error}
          </p>
          <div className="page-actions">
            <Link className="connect-button" href="/">
              Back to Today
            </Link>
          </div>
        </section>
      ) : (
        <CourseBoard courses={courses ?? []} items={items ?? []} />
      )}
    </div>
  );
}

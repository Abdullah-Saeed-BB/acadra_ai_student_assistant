import type { Metadata } from "next";
import { PlannedView } from "@/components/planned-view";

export const metadata: Metadata = {
  title: "Courses",
};

export default function CoursesPage() {
  return (
    <PlannedView
      title="Courses"
      description="Your courses with the academic items they contain — assignments, exams, readings, and announcements — with due dates and review state."
    />
  );
}

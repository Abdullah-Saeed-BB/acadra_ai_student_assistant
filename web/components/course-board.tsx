import Link from "next/link";
import type { AcademicItem, Course } from "@/lib/academics";
import {
  CourseEditButton,
  DeleteRecordButton,
  ItemCreateButton,
  ItemEditButton,
} from "@/components/academic-dialogs";

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/** Render an ISO date in the user's local timezone. */
export function formatDate(iso: string | null): string {
  if (!iso) return "No date";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
    if (!match) return iso;
    const [, year, month, day] = match;
    const name = MONTHS[Number(month) - 1] ?? month;
    return `${name} ${Number(day)}, ${year}`;
  }
  const year = date.getFullYear();
  const month = MONTHS[date.getMonth()] ?? String(date.getMonth() + 1);
  const day = date.getDate();
  return `${month} ${day}, ${year}`;
}

/** Render an ISO timestamp in the user's local timezone. */
export function formatDateTime(iso: string | null): string {
  if (!iso) return "No date";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const year = date.getFullYear();
  const month = MONTHS[date.getMonth()] ?? String(date.getMonth() + 1);
  const day = date.getDate();
  let hours = date.getHours();
  const minutes = date.getMinutes();
  const meridiem = hours >= 12 ? "PM" : "AM";
  hours = hours % 12 || 12;
  return `${year} ${month} ${day} ${hours}:${String(minutes).padStart(2, "0")} ${meridiem}`;
}

export function itemTypeLabel(type: string): string {
  return type ? type[0].toUpperCase() + type.slice(1) : type;
}

function ItemRow({ item, courses }: { item: AcademicItem; courses: Course[] }) {
  return (
    <li className="item-row">
      <div className="item-row-main">
        <span className="item-type">{itemTypeLabel(item.item_type)}</span>
        <Link className="page-link item-title" href={`/items/${item.id}`}>
          {item.title}
        </Link>
        <span className="item-due tnum">{formatDate(item.due_at)}</span>
        <span className={`review-pill is-${item.review_state}`}>
          {itemTypeLabel(item.review_state)}
        </span>
      </div>
      <div className="item-row-actions">
        <ItemEditButton item={item} courses={courses} />
        <DeleteRecordButton kind="item" id={item.id} name={item.title} />
      </div>
    </li>
  );
}

/**
 * The Courses view: each course is a container with the academic items it
 * owns, plus the controls that create, edit, and delete courses and items.
 * Manually recorded items with no course are grouped last so nothing hides.
 */
export function CourseBoard({
  courses,
  items,
}: {
  courses: Course[];
  items: AcademicItem[];
}) {
  const byCourse = new Map<string, AcademicItem[]>();
  const unassigned: AcademicItem[] = [];
  for (const item of items) {
    if (item.course_id) {
      const list = byCourse.get(item.course_id) ?? [];
      list.push(item);
      byCourse.set(item.course_id, list);
    } else {
      unassigned.push(item);
    }
  }

  if (courses.length === 0 && unassigned.length === 0) {
    return (
      <section className="panel empty">
        <h2>No courses yet</h2>
        <p className="panel-note">
          Add a course to group the assignments, readings, and announcements you
          record by hand or import from a source.
        </p>
      </section>
    );
  }

  return (
    <div className="course-board">
      {courses.map((course) => {
        const courseItems = byCourse.get(course.id) ?? [];
        return (
          <section className="panel course-block" key={course.id} aria-labelledby={`course-${course.id}`}>
            <div className="course-head">
              <div className="course-head-text">
                <h2 id={`course-${course.id}`} className="course-title">
                  {course.name}
                </h2>
                <p className="course-meta">
                  {course.code ? `${course.code} · ` : ""}
                  {course.term ?? "No term"} ·{" "}
                  <span className="tnum">
                    {course.item_count} {course.item_count === 1 ? "item" : "items"}
                  </span>
                </p>
              </div>
              <div className="course-actions">
                <ItemCreateButton courseId={course.id} courses={courses} />
                <CourseEditButton course={course} />
                <DeleteRecordButton kind="course" id={course.id} name={course.name} />
              </div>
            </div>

            {courseItems.length > 0 ? (
              <ul className="item-list">
                {courseItems.map((item) => (
                  <ItemRow key={item.id} item={item} courses={courses} />
                ))}
              </ul>
            ) : (
              <p className="panel-note course-empty">
                No items in this course yet. Add one, or link an existing item by
                editing it.
              </p>
            )}
          </section>
        );
      })}

      {unassigned.length > 0 ? (
        <section className="panel course-block" aria-labelledby="course-unassigned">
          <div className="course-head">
            <div className="course-head-text">
              <h2 id="course-unassigned" className="course-title">
                No course yet
              </h2>
              <p className="course-meta">
                Items you recorded without a course. Edit one to assign it.
              </p>
            </div>
          </div>
          <ul className="item-list">
            {unassigned.map((item) => (
              <ItemRow key={item.id} item={item} courses={courses} />
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

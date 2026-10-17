import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { CollapsibleSection } from "@/components/collapsible-section";
import { formatDate, itemTypeLabel } from "@/components/course-board";
import {
  ItemEditButton,
  DeleteRecordButton,
} from "@/components/academic-dialogs";
import {
  backendUnavailableMessage,
  listAcademicItems,
  listChanges,
  listCourses,
  type Change,
  type Course,
} from "@/lib/academics";

export const metadata: Metadata = {
  title: "Inbox",
};

const IGNORED_CHANGE_KEYS = new Set(["_correction_note"]);

function formatChangeValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** A compact before → after view of the fields a change event touched. */
function ChangeDiff({ change }: { change: Change }) {
  if (change.change_kind === "created") {
    return (
      <p className="change-diff">
        Recorded a new {itemTypeLabel(change.item_type ?? "item").toLowerCase()}
        .
      </p>
    );
  }

  const before = change.before_values ?? {};
  const after = change.after_values ?? {};
  const changed = Object.keys(after).filter(
    (key) =>
      !IGNORED_CHANGE_KEYS.has(key) &&
      JSON.stringify(before[key] ?? null) !==
        JSON.stringify(after[key] ?? null),
  );

  if (changed.length === 0) return <p className="change-diff">Updated.</p>;

  return (
    <ul className="change-diff">
      {changed.map((key) => (
        <li key={key}>
          <span className="change-field">{key.replace(/_/g, " ")}</span>
          <span className="change-before">
            {formatChangeValue(before[key] ?? null)}
          </span>
          <span className="change-arrow" aria-hidden="true">
            →
          </span>
          <span className="change-after">{formatChangeValue(after[key])}</span>
        </li>
      ))}
    </ul>
  );
}

export default async function InboxPage() {
  let changes = null;
  let items = null;
  let courses: Course[] = [];
  let error: string | null = null;
  try {
    const [changePage, itemPage, coursePage] = await Promise.all([
      listChanges("limit=50"),
      listAcademicItems("limit=20"),
      listCourses("limit=100"),
    ]);
    changes = changePage.items;
    items = itemPage.items;
    courses = coursePage.items;
  } catch (cause) {
    error =
      cause instanceof Error ? cause.message : backendUnavailableMessage();
  }

  const changeList = changes ?? [];
  const itemList = items ?? [];

  return (
    <div className="page">
      <PageHeader
        title="Inbox"
        description="Recent academic records and the changes recorded against them."
        tooltip="An academic item is a tracked fact from a source — an assignment, announcement, reading, or event — with its course, dates, review state, and the source evidence behind it. The inbox lists these records and the changes recorded against them.">
        <Link className="connect-button" href="/courses">
          Manage courses
        </Link>
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
        <>
          <CollapsibleSection
            id="inbox-changes"
            title="Recent changes"
            empty={itemList.length === 0}>
            {changeList.length === 0 ? (
              <p className="panel-note">
                No changes yet. Changes appear here when a source is processed
                or you record, edit, or correct an academic item.
              </p>
            ) : (
              <ul className="change-list">
                {changeList.map((change) => (
                  <li className="change-row" key={change.id}>
                    <div className="change-head">
                      <Link
                        className="page-link"
                        href={`/items/${change.academic_item_id}`}>
                        {change.title ?? "Untitled item"}
                      </Link>
                      <span className={`change-badge is-${change.change_kind}`}>
                        {change.change_kind}
                      </span>
                      <span className="change-origin">
                        {change.origin.replace(/_/g, " ")}
                      </span>
                      <span className="change-date tnum">
                        {formatDate(change.recorded_at)}
                      </span>
                    </div>
                    <ChangeDiff change={change} />
                  </li>
                ))}
              </ul>
            )}
          </CollapsibleSection>

          <CollapsibleSection
            id="inbox-items"
            title="Recent academic items"
            empty={itemList.length === 0}>
            {itemList.length === 0 ? (
              <p className="panel-note">
                No academic items yet. Add a source or record one by hand on the
                Courses page.
              </p>
            ) : (
              <ul className="item-list">
                {itemList.map((item) => (
                  <li className="item-row" key={item.id}>
                    <div className="item-row-main">
                      <span className="item-type">
                        {itemTypeLabel(item.item_type)}
                      </span>
                      <Link
                        className="page-link item-title"
                        href={`/items/${item.id}`}>
                        {item.title}
                      </Link>
                      <span className="item-due tnum">
                        {formatDate(item.due_at)}
                      </span>
                      <span className={`review-pill is-${item.review_state}`}>
                        {itemTypeLabel(item.review_state)}
                      </span>
                    </div>
                    <div className="item-row-actions">
                      <ItemEditButton item={item} courses={courses} />
                      <DeleteRecordButton kind="item" id={item.id} name={item.title} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CollapsibleSection>
        </>
      )}
    </div>
  );
}

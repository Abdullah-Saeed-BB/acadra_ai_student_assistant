import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { formatDate, itemTypeLabel } from "@/components/course-board";
import { DeleteRecordButton, ItemEditButton } from "@/components/academic-dialogs";
import {
  backendUnavailableMessage,
  getAcademicItem,
  getAcademicItemEvidence,
  listCourses,
  type AcademicServiceError,
  type Course,
} from "@/lib/academics";

export const metadata: Metadata = {
  title: "Academic item",
};

function percentLabel(value: string | null): string {
  return value === null ? "Not set" : `${Number(value)}%`;
}

export default async function AcademicItemPage({
  params,
}: {
  params: Promise<{ item_id: string }>;
}) {
  const { item_id } = await params;

  let detail = null;
  let evidence = null;
  let courses: Course[] = [];
  let error: string | null = null;
  try {
    detail = await getAcademicItem(item_id);
    const [itemEvidence, coursePage] = await Promise.all([
      getAcademicItemEvidence(item_id),
      listCourses("limit=100"),
    ]);
    evidence = itemEvidence;
    courses = coursePage.items;
  } catch (cause) {
    if ((cause as AcademicServiceError)?.status === 404) notFound();
    error = cause instanceof Error ? cause.message : backendUnavailableMessage();
  }

  if (error || !detail) {
    return (
      <div className="page">
        <PageHeader title="Academic item" />
        <section className="panel">
          <p className="message error" role="alert">
            {error ?? backendUnavailableMessage()}
          </p>
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

  return (
    <div className="page">
      <PageHeader
        title="Academic item"
        description="One record: its type, course, dates, and review state, with any source evidence that produced it.">
        <ItemEditButton item={detail} courses={courses} />
        <DeleteRecordButton
          kind="item"
          id={detail.id}
          name={detail.title}
          redirectTo="/courses"
        />
      </PageHeader>

      <section className="panel">
        <h2 className="detail-title">{detail.title}</h2>
        <dl className="detail-grid">
          <div>
            <dt>Type</dt>
            <dd>{itemTypeLabel(detail.item_type)}</dd>
          </div>
          <div>
            <dt>Course</dt>
            <dd>
              {detail.course ? (
                <Link className="page-link" href="/courses">
                  {detail.course.code ? `${detail.course.code} · ` : ""}
                  {detail.course.name}
                </Link>
              ) : (
                "No course"
              )}
            </dd>
          </div>
          <div>
            <dt>Due</dt>
            <dd className="tnum">{formatDate(detail.due_at)}</dd>
          </div>
          <div>
            <dt>Starts</dt>
            <dd className="tnum">{formatDate(detail.starts_at)}</dd>
          </div>
          <div>
            <dt>Grade weight</dt>
            <dd className="tnum">{percentLabel(detail.grade_weight_percent)}</dd>
          </div>
          <div>
            <dt>Late penalty</dt>
            <dd>{detail.late_penalty ?? "Not set"}</dd>
          </div>
          <div>
            <dt>Review state</dt>
            <dd>
              <span className={`review-pill is-${detail.review_state}`}>
                {itemTypeLabel(detail.review_state)}
              </span>
            </dd>
          </div>
          <div>
            <dt>Added</dt>
            <dd className="tnum">{formatDate(detail.created_at)}</dd>
          </div>
        </dl>

        {detail.details ? (
          <p className="detail-details">{detail.details}</p>
        ) : (
          <p className="panel-note">No details recorded for this item.</p>
        )}
      </section>

      <section className="panel" aria-labelledby="item-evidence">
        <h2 id="item-evidence">Source evidence</h2>
        {evidence ? (
          <>
            <dl className="detail-grid">
              <div>
                <dt>Source</dt>
                <dd>{evidence.source_title ?? "Untitled source"}</dd>
              </div>
              <div>
                <dt>Type</dt>
                <dd>{itemTypeLabel(evidence.source_type)}</dd>
              </div>
              <div>
                <dt>Observed</dt>
                <dd className="tnum">{formatDate(evidence.observed_at)}</dd>
              </div>
              {evidence.original_ref ? (
                <div>
                  <dt>Reference</dt>
                  <dd className="detail-ref">{evidence.original_ref}</dd>
                </div>
              ) : null}
            </dl>

            {Object.entries(evidence.evidence).length > 0 ? (
              <ul className="evidence-list">
                {Object.entries(evidence.evidence).map(([field, excerpt]) => (
                  <li key={field}>
                    <span className="evidence-field">{field}</span>
                    <span className="evidence-excerpt">{excerpt ?? "—"}</span>
                  </li>
                ))}
              </ul>
            ) : null}

            {evidence.review_reasons.length > 0 ? (
              <div className="evidence-reasons">
                <h3>Review reasons</h3>
                <ul>
                  {evidence.review_reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        ) : (
          <p className="panel-note">
            This item was recorded by hand. It has no source revision or
            extracted evidence.
          </p>
        )}
      </section>

      <div className="page-actions">
        <Link className="connect-button" href="/courses">
          Courses
        </Link>
        <Link className="page-link" href="/inbox">
          Inbox
        </Link>
      </div>
    </div>
  );
}

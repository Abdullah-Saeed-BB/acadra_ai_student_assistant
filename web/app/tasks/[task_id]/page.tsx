import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { TaskCard } from "@/components/task-card";
import {
  backendUnavailableMessage,
  getTask,
  type TaskServiceError,
} from "@/lib/tasks";

export const metadata: Metadata = {
  title: "Task detail",
};

export default async function TaskDetailPage({
  params,
}: {
  params: Promise<{ task_id: string }>;
}) {
  const { task_id } = await params;

  let detail = null;
  let error: string | null = null;
  try {
    detail = await getTask(task_id);
  } catch (cause) {
    if ((cause as TaskServiceError)?.status === 404) notFound();
    error = cause instanceof Error ? cause.message : backendUnavailableMessage();
  }

  if (error || !detail) {
    return (
      <div className="page">
        <PageHeader title="Task detail" />
        <section className="panel">
          <p className="message error" role="alert">
            {error ?? backendUnavailableMessage()}
          </p>
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

  const { progress } = detail;

  return (
    <div className="page">
      <PageHeader
        title="Task detail"
        description="The full task, with everything linked to it and any steps you have split out."
      />

      <TaskCard task={detail} size="large" linkTitle={false}>
        <dl className="task-card-meta">
          <div>
            <dt>Academic item</dt>
            <dd>
              {detail.academic_item ? (
                <Link
                  className="page-link"
                  href={`/items/${detail.academic_item.id}`}
                >
                  {detail.academic_item.title}
                </Link>
              ) : (
                "None linked"
              )}
            </dd>
          </div>
          {detail.academic_item?.item_type ? (
            <div>
              <dt>Type</dt>
              <dd>{detail.academic_item.item_type}</dd>
            </div>
          ) : null}
          {detail.academic_item?.due_at ? (
            <div>
              <dt>Due</dt>
              <dd className="tnum">{detail.academic_item.due_at}</dd>
            </div>
          ) : null}
          {detail.course ? (
            <div>
              <dt>Course</dt>
              <dd>
                {detail.course.code ? `${detail.course.code} · ` : ""}
                {detail.course.name}
              </dd>
            </div>
          ) : null}
          {detail.parent_task_id ? (
            <div>
              <dt>Parent</dt>
              <dd>
                <Link
                  className="page-link"
                  href={`/tasks/${detail.parent_task_id}`}
                >
                  Parent task
                </Link>
              </dd>
            </div>
          ) : null}
        </dl>
      </TaskCard>

      <section className="task-steps" aria-labelledby="task-steps-title">
        <h2 id="task-steps-title">
          {progress.total_steps > 0
            ? `${progress.unfinished_steps} of ${progress.total_steps} steps remaining`
            : "No steps yet"}
        </h2>
        {detail.steps.length > 0 ? (
          <div className="task-cards">
            {detail.steps.map((step) => (
              <TaskCard key={step.id} task={step} titleAs="h3" />
            ))}
          </div>
        ) : (
          <p className="panel-note">
            This task has no steps. Split it into smaller steps to track progress
            piece by piece.
          </p>
        )}
      </section>

      <div className="page-actions">
        <Link className="connect-button" href="/tasks">
          All tasks
        </Link>
        <Link className="page-link" href="/">
          Back to Today
        </Link>
      </div>
    </div>
  );
}

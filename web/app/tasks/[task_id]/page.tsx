import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { TaskCard } from "@/components/task-card";
import { TaskGroup } from "@/components/task-group";
import { TaskCreateButton } from "@/components/task-create";
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

  // Steps are one level deep and are shown inside their top-level task; they do
  // not have a detail page of their own.
  if (detail.parent_task_id) notFound();

  const { progress } = detail;

  return (
    <div className="page">
      <PageHeader
        title="Task detail"
        description="The full task, with everything linked to it and any steps you have split out."
      />

      <TaskCard task={detail} size="large" linkTitle={false} />

      <section className="task-steps" aria-labelledby="task-steps-title">
        <div className="task-steps-head">
          <h2 id="task-steps-title">
            {progress.total_steps > 0
              ? `${progress.unfinished_steps} of ${progress.total_steps} steps remaining`
              : "No steps yet"}
          </h2>
          <TaskCreateButton
            label="Add step"
            heading="New step"
            submitLabel="Add step"
            parentTaskId={detail.id}
            defaultDay={detail.selected_day ?? ""}
          />
        </div>
        {detail.steps.length > 0 ? (
          <TaskGroup tasks={detail.steps} titleAs="h3" allowStepReorder />
        ) : (
          <p className="panel-note">
            This task has no steps yet. Add a step to break it into smaller
            pieces you can track.
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

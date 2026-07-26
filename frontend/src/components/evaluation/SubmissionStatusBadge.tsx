import { Badge } from "@/components/ui/badge";
import type { Submission, SubmissionStatus } from "@/lib/types";

const STATUS_CONFIG: Record<SubmissionStatus, { label: string; variant: "secondary" | "success" | "degraded" | "default" | "error" }> = {
  pending: { label: "Pending", variant: "secondary" },
  cloning: { label: "Cloning", variant: "default" },
  analyzing: { label: "Analyzing", variant: "default" },
  evaluating: { label: "Evaluating", variant: "default" },
  completed: { label: "Completed", variant: "success" },
  failed: { label: "Failed", variant: "error" },
};

export function SubmissionStatusBadge({ submission }: { submission: Pick<Submission, "status" | "degraded"> }) {
  if (submission.status === "completed" && submission.degraded) {
    return <Badge variant="degraded">Degraded</Badge>;
  }
  const config = STATUS_CONFIG[submission.status];
  return <Badge variant={config.variant}>{config.label}</Badge>;
}

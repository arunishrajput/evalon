import { Badge } from "@/components/ui/badge";
import type { HackathonStatus } from "@/lib/types";

const STATUS_CONFIG: Record<HackathonStatus, { label: string; variant: "secondary" | "success" | "degraded" | "default" }> = {
  draft: { label: "Draft", variant: "secondary" },
  active: { label: "Active", variant: "success" },
  evaluating: { label: "Evaluating", variant: "degraded" },
  finalized: { label: "Finalized", variant: "default" },
};

export function StatusBadge({ status }: { status: HackathonStatus }) {
  const config = STATUS_CONFIG[status];
  return <Badge variant={config.variant}>{config.label}</Badge>;
}

"use client";

import useSWR from "swr";
import { CheckCircle2, Clock, FileStack, Loader2, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AnimatedNumber } from "./AnimatedNumber";
import { ScoreHistogram } from "./ScoreHistogram";
import { TechStackCloud } from "./TechStackCloud";
import { useDashboardStream } from "@/hooks/useDashboardStream";
import { adminApi, dashboardApi } from "@/lib/api";
import { cn, formatScore } from "@/lib/utils";

const STAT_CARDS = [
  { key: "total_submissions" as const, label: "Submissions", icon: FileStack, color: "text-white" },
  { key: "evaluations_completed" as const, label: "Completed", icon: CheckCircle2, color: "text-emerald-400" },
  { key: "evaluations_in_progress" as const, label: "In progress", icon: Loader2, color: "text-accent" },
  { key: "evaluations_queued" as const, label: "Queued", icon: Clock, color: "text-degraded" },
  { key: "evaluations_failed" as const, label: "Failed", icon: XCircle, color: "text-error" },
];

export function LiveDashboard({ hackathonId }: { hackathonId: string }) {
  const { data: initial } = useSWR(["dashboard-snapshot", hackathonId], () => dashboardApi.get(hackathonId));
  const { stats, connected } = useDashboardStream(hackathonId, initial ?? null);
  const { data: modelStatus } = useSWR("model-status", adminApi.modelStatus, { refreshInterval: 5_000 });

  const modelDotColor = !modelStatus
    ? "bg-gray-600"
    : modelStatus.lock_held_by
      ? modelStatus.queue_depth > 0
        ? "bg-degraded"
        : "bg-accent"
      : "bg-emerald-500";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span className={cn("h-2 w-2 rounded-full", connected ? "animate-pulse bg-emerald-500" : "bg-gray-600")} />
        {connected ? "Live" : "Connecting..."}
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        {STAT_CARDS.map((card) => (
          <Card key={card.key}>
            <CardContent className="flex flex-col items-center justify-center gap-1 pt-6 text-center">
              <card.icon className={cn("h-4 w-4", card.color)} />
              <AnimatedNumber value={stats?.[card.key] ?? "—"} className="text-3xl font-bold text-white" />
              <div className="text-xs text-gray-500">{card.label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Score distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ScoreHistogram distribution={stats?.score_distribution ?? {}} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top tech stacks</CardTitle>
          </CardHeader>
          <CardContent>
            <TechStackCloud frequency={stats?.tech_stack_frequency ?? {}} />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top 5 leaderboard preview</CardTitle>
          </CardHeader>
          <CardContent>
            {!stats?.top5_preview?.length && <p className="text-sm text-gray-500">No completed evaluations yet.</p>}
            <ol className="space-y-2">
              {stats?.top5_preview?.map((entry) => (
                <li key={entry.rank} className="flex items-center justify-between rounded-md bg-white/5 px-3 py-2 text-sm">
                  <span className="text-gray-300">
                    <span className="mr-2 font-bold text-white">#{entry.rank}</span>
                    {entry.repo_name || "Untitled"}
                  </span>
                  <span className="font-medium text-white">{formatScore(entry.score)}</span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Model queue status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center gap-2">
              <span className={cn("h-2.5 w-2.5 rounded-full", modelDotColor, modelStatus?.lock_held_by && "animate-pulse")} />
              <span className="text-gray-300">
                {modelStatus?.inference_model || "qwen2.5-coder:7b"}{" "}
                {modelStatus?.inference_model_loaded ? "● Loaded" : "○ Not loaded"}
              </span>
            </div>
            <div className="text-gray-400">
              Queue depth: <span className="text-white">{modelStatus?.queue_depth ?? 0}</span> evaluation(s) pending
            </div>
            {modelStatus?.estimated_wait_seconds ? (
              <div className="text-gray-400">
                Estimated wait: <span className="text-white">~{Math.round(modelStatus.estimated_wait_seconds / 60)} min</span>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

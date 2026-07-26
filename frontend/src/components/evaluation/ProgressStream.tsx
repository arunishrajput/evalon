"use client";

import { useEffect } from "react";
import { AlertTriangle, CheckCircle2, Circle, Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { DegradedBanner } from "@/components/states/DegradedBanner";
import { useEvaluationStream } from "@/hooks/useEvaluationStream";
import { formatDuration } from "@/lib/utils";
import type { ProgressStage } from "@/lib/types";

const STAGE_ORDER: { stage: ProgressStage; label: string }[] = [
  { stage: "cloning", label: "Cloning repository" },
  { stage: "analyzing", label: "Static analysis" },
  { stage: "agent_repo_understanding", label: "Repository understanding" },
  { stage: "agent_code_quality", label: "Code quality" },
  { stage: "agent_innovation", label: "Innovation" },
  { stage: "agent_comparative", label: "Comparative analysis" },
  { stage: "generating_report", label: "Generating report" },
];

interface ProgressStreamProps {
  submissionId: string;
  submittedAt: string;
  onCompleted?: () => void;
}

export function ProgressStream({ submissionId, submittedAt, onCompleted }: ProgressStreamProps) {
  const { latest, terminal, connectionError, events } = useEvaluationStream(submissionId);

  const currentStageIndex = latest?.event === "progress" ? STAGE_ORDER.findIndex((s) => s.stage === latest.data.stage) : -1;
  const progressPct = latest?.event === "progress" ? latest.data.progress_pct : latest?.event === "completed" ? 100 : 0;
  const completedEvent = events.find((e) => e.event === "completed");
  const errorEvent = events.find((e) => e.event === "error");
  const degradedEvents = events.filter((e) => e.event === "degraded");

  useEffect(() => {
    if (terminal && completedEvent?.event === "completed") onCompleted?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [terminal, completedEvent]);

  if (terminal && completedEvent?.event === "completed") {
    return (
      <Card>
        <CardContent className="flex items-center justify-between py-4">
          <div className="flex items-center gap-2 text-sm text-gray-300">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            Evaluated in {formatDuration(submittedAt, completedEvent.data.timestamp) || "a few seconds"}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="space-y-4 py-6">
        {connectionError && <p className="text-sm text-gray-500">Reconnecting to progress stream...</p>}
        {errorEvent?.event === "error" && (
          <div className="flex items-center gap-2 rounded-md border border-error/30 bg-error/10 px-3 py-2 text-sm text-red-200">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {errorEvent.data.message}
          </div>
        )}

        {degradedEvents.map((e, i) =>
          e.event === "degraded" ? <DegradedBanner key={i} message={e.data.message} /> : null
        )}

        <Progress value={progressPct} />

        <ol className="space-y-3">
          {STAGE_ORDER.map((step, index) => {
            const isDone = currentStageIndex > index || terminal;
            const isActive = currentStageIndex === index && !terminal;
            return (
              <li key={step.stage} className="flex items-center gap-3 text-sm">
                {isDone ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                ) : isActive ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-accent" />
                ) : (
                  <Circle className="h-4 w-4 shrink-0 text-gray-700" />
                )}
                <span className={isActive ? "font-medium text-white" : isDone ? "text-gray-400" : "text-gray-600"}>
                  {step.label}
                </span>
              </li>
            );
          })}
        </ol>

        {latest?.event === "progress" && <p className="text-xs text-gray-500">{latest.data.message}</p>}
      </CardContent>
    </Card>
  );
}

"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { Download, MessageCircle, Printer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DegradedBanner } from "@/components/states/DegradedBanner";
import { SubmissionStatusBadge } from "@/components/evaluation/SubmissionStatusBadge";
import { ProgressStream } from "@/components/evaluation/ProgressStream";
import { ScoreRadarChart, findAgentResult } from "@/components/evaluation/ScoreRadarChart";
import { ScoreTooltip } from "@/components/evaluation/ScoreTooltip";
import { HowYouCompare } from "@/components/evaluation/HowYouCompare";
import { ReportViewer } from "@/components/evaluation/ReportViewer";
import { PrintableReport } from "@/components/evaluation/PrintableReport";
import { evaluationApi, submissionApi, API_BASE } from "@/lib/api";
import { formatScore, scoreColor } from "@/lib/utils";
import { useAuthStore } from "@/store/auth";
import type { EvaluationReport } from "@/lib/types";

export default function EvaluationPage({ params }: { params: { submissionId: string } }) {
  const { submissionId } = params;
  const [activeCriterion, setActiveCriterion] = useState<string | null>(null);
  const { accessToken, user } = useAuthStore();

  const {
    data: submission,
    mutate: mutateSubmission,
    isLoading: submissionLoading,
  } = useSWR(["submission", submissionId], () => submissionApi.get(submissionId));

  const shouldFetchEvaluation = submission?.status === "completed";
  const { data: evaluation, mutate: mutateEvaluation } = useSWR(
    shouldFetchEvaluation ? ["evaluation", submissionId] : null,
    () => evaluationApi.get(submissionId)
  );

  const handleRefetch = () => {
    mutateSubmission();
    mutateEvaluation();
  };

  const handlePrint = () => {
    document.body.classList.add("printing-report");
    window.print();
    document.body.classList.remove("printing-report");
  };

  const handleDownloadPdf = async () => {
    if (!accessToken) return;
    const res = await fetch(`${API_BASE}/evaluations/${submissionId}/export`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `evalon-report-${submissionId}.pdf`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (submissionLoading) return <p className="text-gray-500">Loading...</p>;
  if (!submission) return <p className="text-gray-500">Submission not found.</p>;

  const report = evaluation?.report;
  const isPending = submission.status !== "completed" && submission.status !== "failed";

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-start justify-between print:hidden">
        <div>
          <h1 className="text-xl font-bold text-white">{submission.repo_name || submission.repo_url}</h1>
          <a href={submission.repo_url} target="_blank" rel="noreferrer" className="text-sm text-gray-500 hover:underline">
            {submission.repo_url}
          </a>
        </div>
        <div className="flex items-center gap-2">
          <SubmissionStatusBadge submission={submission} />
          {submission.status === "completed" && (
            <Button asChild variant="outline" size="sm">
              <Link href={`/participant/mentor/${submissionId}`}>
                <MessageCircle className="mr-1 h-4 w-4" />
                Ask mentor
              </Link>
            </Button>
          )}
        </div>
      </div>

      {isPending && (
        <div className="print:hidden">
          <ProgressStream submissionId={submissionId} submittedAt={submission.submitted_at} onCompleted={handleRefetch} />
        </div>
      )}

      {submission.status === "failed" && (
        <Card className="print:hidden">
          <CardContent className="py-8 text-center">
            <p className="mb-1 font-medium text-white">Evaluation could not be completed</p>
            <p className="text-sm text-gray-400">{submission.error_message || "Please contact the hackathon admin."}</p>
          </CardContent>
        </Card>
      )}

      {submission.status === "completed" && report && evaluation && (
        <div className="space-y-8">
          <div className="print:hidden">
            <div className="mb-6 flex flex-col items-center gap-2 text-center">
              <span className={`text-7xl font-bold ${scoreColor(Number(evaluation.final_score))}`}>
                {formatScore(evaluation.final_score)}
              </span>
              <span className="text-sm text-gray-500">out of 100</span>
              {report.degraded && <DegradedBanner message={report.degraded_explanation} />}
            </div>

            <div className="mb-4 flex items-center justify-end gap-2">
              <Button variant="outline" size="sm" onClick={handleDownloadPdf}>
                <Download className="mr-1 h-4 w-4" />
                Download report (PDF)
              </Button>
              <Button variant="outline" size="sm" onClick={handlePrint}>
                <Printer className="mr-1 h-4 w-4" />
                Print report
              </Button>
            </div>

            <Card>
              <CardContent className="pt-6">
                <ScoreRadarChart
                  byCriterion={report.scores.by_criterion}
                  comparative={report.comparative}
                  onAxisClick={setActiveCriterion}
                />
                {activeCriterion && (
                  <div className="mt-2 flex justify-center">
                    <ActiveCriterionTooltip
                      report={report}
                      criterion={activeCriterion}
                      onClose={() => setActiveCriterion(null)}
                    />
                  </div>
                )}
                <div className="mt-4 space-y-1">
                  {report.scores.by_criterion.map((c) => {
                    const agent = findAgentResult(report.agent_results, c.agent_id || undefined);
                    return (
                      <ScoreTooltip
                        key={c.criterion}
                        criterion={c.criterion}
                        score={c.score}
                        topEvidence={agent?.top_evidence || []}
                      >
                        <div className="flex items-center justify-between rounded-md px-3 py-2 text-sm hover:bg-white/5">
                          <span className="text-gray-300">{c.criterion}</span>
                          <span className="font-medium text-white">{formatScore(c.score)}</span>
                        </div>
                      </ScoreTooltip>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            <div className="mt-6">
              <h2 className="mb-3 text-sm font-semibold text-white">How you compare</h2>
              <HowYouCompare comparative={report.comparative} />
            </div>

            <div className="mt-8">
              <ReportViewer report={report} />
            </div>
          </div>

          <PrintableReport
            report={report}
            repoName={submission.repo_name || submission.repo_url}
            participantName={submission.user_id === user?.id ? user?.full_name || user?.email || "Participant" : "Participant"}
            finalScore={evaluation.final_score}
            submissionId={submissionId}
          />
        </div>
      )}
    </div>
  );
}

function ActiveCriterionTooltip({
  report,
  criterion,
  onClose,
}: {
  report: EvaluationReport;
  criterion: string;
  onClose: () => void;
}) {
  const entry = report.scores.by_criterion.find((c) => c.criterion === criterion);
  const agent = findAgentResult(report.agent_results, entry?.agent_id || undefined);
  if (!entry) return null;
  return (
    <div className="w-full max-w-sm rounded-md border border-white/10 bg-card-elevated p-4 text-sm">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-semibold text-white">{criterion}</span>
        <button onClick={onClose} className="text-xs text-gray-500 hover:text-white">
          Close
        </button>
      </div>
      <p className="mb-2 text-lg font-bold text-accent">{formatScore(entry.score)} / 100</p>
      <ul className="space-y-1 text-gray-300">
        {(agent?.top_evidence || []).slice(0, 2).map((item, i) => (
          <li key={i}>• {item}</li>
        ))}
      </ul>
    </div>
  );
}

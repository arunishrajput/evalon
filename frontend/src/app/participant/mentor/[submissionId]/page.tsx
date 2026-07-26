"use client";

import useSWR from "swr";
import { Trophy } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DegradedBanner } from "@/components/states/DegradedBanner";
import { MentorUnavailableState } from "@/components/states/MentorUnavailableState";
import { ChatInterface } from "@/components/mentor/ChatInterface";
import { chatApi, evaluationApi, submissionApi } from "@/lib/api";
import { formatScore, scoreColor } from "@/lib/utils";

export default function MentorPage({ params }: { params: { submissionId: string } }) {
  const { submissionId } = params;
  const { data: submission } = useSWR(["submission", submissionId], () => submissionApi.get(submissionId));
  const { data: session, isLoading: sessionLoading } = useSWR(["chat-session", submissionId], () =>
    chatApi.createSession(submissionId)
  );
  const { data: evaluation } = useSWR(
    session?.mentor_available ? ["evaluation", submissionId] : null,
    () => evaluationApi.get(submissionId)
  );

  if (sessionLoading || !submission) return <p className="text-gray-500">Loading...</p>;

  return (
    <div className="mx-auto grid max-w-5xl gap-6 lg:grid-cols-[280px_1fr]">
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{submission.repo_name || submission.repo_url}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {evaluation && (
              <>
                <div className="text-center">
                  <span className={`text-4xl font-bold ${scoreColor(Number(evaluation.final_score))}`}>
                    {formatScore(evaluation.final_score)}
                  </span>
                  <p className="text-xs text-gray-500">Overall score</p>
                </div>
                {evaluation.report?.degraded && <DegradedBanner message={evaluation.report.degraded_explanation} />}
                {evaluation.report?.comparative?.sufficient_data && (
                  <div className="flex items-center justify-center gap-2 rounded-md bg-white/5 px-3 py-2 text-sm">
                    <Trophy className="h-4 w-4 text-accent" />
                    <span className="text-gray-300">
                      Rank #{evaluation.report.comparative.rank_in_pool} · {evaluation.report.comparative.percentile_label}
                    </span>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <div>
        {session && !session.mentor_available ? (
          <MentorUnavailableState reason={session.unavailable_reason} />
        ) : (
          <ChatInterface submissionId={submissionId} />
        )}
      </div>
    </div>
  );
}

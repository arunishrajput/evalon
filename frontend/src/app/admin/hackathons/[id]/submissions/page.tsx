"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SubmissionStatusBadge } from "@/components/evaluation/SubmissionStatusBadge";
import { hackathonApi, evaluationApi } from "@/lib/api";
import { formatScore } from "@/lib/utils";
import type { Submission } from "@/lib/types";

function ScoreCell({ submission }: { submission: Submission }) {
  const { data: evaluation } = useSWR(
    submission.status === "completed" ? ["evaluation", submission.id] : null,
    () => evaluationApi.get(submission.id)
  );
  if (submission.status !== "completed") return <span className="text-gray-600">—</span>;
  return <span className="font-medium text-white">{formatScore(evaluation?.final_score)}</span>;
}

export default function SubmissionsPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const { data: submissions, isLoading } = useSWR(["submissions", id], () => hackathonApi.listSubmissions(id), {
    refreshInterval: 10_000,
  });
  const [selected, setSelected] = useState<string[]>([]);

  const toggle = (submissionId: string) => {
    setSelected((prev) =>
      prev.includes(submissionId)
        ? prev.filter((s) => s !== submissionId)
        : prev.length < 3
          ? [...prev, submissionId]
          : prev
    );
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Submissions</h1>
        <Button asChild disabled={selected.length < 2}>
          <Link href={selected.length >= 2 ? `/admin/hackathons/${id}/compare?ids=${selected.join(",")}` : "#"}>
            Compare selected ({selected.length}/3)
          </Link>
        </Button>
      </div>

      {isLoading && <p className="text-gray-500">Loading...</p>}
      {!isLoading && submissions?.length === 0 && <p className="text-gray-500">No submissions yet.</p>}

      {!!submissions?.length && (
        <div className="rounded-lg border border-white/10">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10" />
                <TableHead>Repository</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Submitted</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {submissions.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>
                    <input
                      type="checkbox"
                      checked={selected.includes(s.id)}
                      onChange={() => toggle(s.id)}
                      disabled={selected.length >= 3 && !selected.includes(s.id)}
                      className="h-4 w-4 rounded border-white/20 bg-card-elevated accent-accent"
                    />
                  </TableCell>
                  <TableCell>
                    <div className="font-medium text-white">{s.repo_name || s.repo_url}</div>
                    <div className="text-xs text-gray-500">{s.repo_url}</div>
                  </TableCell>
                  <TableCell>
                    <SubmissionStatusBadge submission={s} />
                  </TableCell>
                  <TableCell>
                    <ScoreCell submission={s} />
                  </TableCell>
                  <TableCell className="text-sm text-gray-400">
                    {new Date(s.submitted_at).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    {s.status === "completed" && (
                      <Link href={`/participant/evaluation/${s.id}`} className="text-sm text-accent hover:underline">
                        View report →
                      </Link>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

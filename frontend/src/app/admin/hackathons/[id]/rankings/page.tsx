"use client";

import useSWR from "swr";
import Link from "next/link";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { rankingApi } from "@/lib/api";
import { formatScore, formatPercentile } from "@/lib/utils";

function downloadCsv(filename: string, rows: (string | number)[][]) {
  const csv = rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export default function RankingsPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const { data: rankings, isLoading, error } = useSWR(["rankings", id], () => rankingApi.leaderboard(id), {
    refreshInterval: 15_000,
  });

  const exportCsv = () => {
    if (!rankings) return;
    downloadCsv(`rankings-${id}.csv`, [
      ["Rank", "Participant", "Repository", "Score", "Percentile", "Finalized"],
      ...rankings.map((r) => [
        r.rank,
        r.participant_name || "Hidden until finalization",
        r.repo_name || "",
        formatScore(r.final_score),
        formatPercentile(r.percentile),
        r.finalized ? "Yes" : "No",
      ]),
    ]);
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Rankings</h1>
        <Button variant="outline" onClick={exportCsv} disabled={!rankings?.length}>
          <Download className="mr-1 h-4 w-4" />
          Export CSV
        </Button>
      </div>

      {isLoading && <p className="text-gray-500">Loading...</p>}
      {error && <p className="text-gray-500">Rankings aren&apos;t available yet — no evaluations have completed.</p>}

      {!!rankings?.length && (
        <div className="rounded-lg border border-white/10">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Rank</TableHead>
                <TableHead>Participant</TableHead>
                <TableHead>Repository</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Percentile</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rankings.map((r) => (
                <TableRow key={r.submission_id}>
                  <TableCell className="font-bold text-white">#{r.rank}</TableCell>
                  <TableCell>{r.participant_name || <span className="text-gray-500">Hidden</span>}</TableCell>
                  <TableCell>{r.repo_name || "—"}</TableCell>
                  <TableCell className="font-medium text-white">{formatScore(r.final_score)}</TableCell>
                  <TableCell>{formatPercentile(r.percentile)}</TableCell>
                  <TableCell>
                    <Badge variant={r.finalized ? "success" : "secondary"}>{r.finalized ? "Finalized" : "Live"}</Badge>
                  </TableCell>
                  <TableCell>
                    <Link href={`/participant/evaluation/${r.submission_id}`} className="text-sm text-accent hover:underline">
                      View →
                    </Link>
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

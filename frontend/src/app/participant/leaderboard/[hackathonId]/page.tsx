"use client";

import useSWR from "swr";
import { Trophy } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { rankingApi, hackathonApi, ApiError } from "@/lib/api";
import { cn, formatPercentile, formatScore } from "@/lib/utils";

export default function LeaderboardPage({ params }: { params: { hackathonId: string } }) {
  const { hackathonId } = params;
  const { data: hackathon } = useSWR(["hackathon", hackathonId], () => hackathonApi.get(hackathonId));
  const { data: rankings, error } = useSWR(["leaderboard", hackathonId], () => rankingApi.leaderboard(hackathonId), {
    refreshInterval: 15_000,
  });

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-center gap-2">
        <Trophy className="h-6 w-6 text-accent" />
        <h1 className="text-2xl font-bold text-white">{hackathon?.title || "Leaderboard"}</h1>
      </div>

      {error && error instanceof ApiError && error.errorCode === "rankings_not_visible" && (
        <Card>
          <CardContent className="py-12 text-center text-gray-400">
            Rankings aren&apos;t available yet — the admin hasn&apos;t finalized results for this hackathon.
          </CardContent>
        </Card>
      )}

      {!!rankings?.length && (
        <div className="rounded-lg border border-white/10">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Rank</TableHead>
                <TableHead>Project</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Percentile</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rankings.map((r) => (
                <TableRow key={r.submission_id} className={cn(r.is_you && "bg-accent/10")}>
                  <TableCell className="font-bold text-white">#{r.rank}</TableCell>
                  <TableCell>
                    {r.repo_name || "Untitled"}
                    {r.is_you && (
                      <Badge variant="default" className="ml-2">
                        You
                      </Badge>
                    )}
                    {r.participant_name && <span className="ml-2 text-xs text-gray-500">{r.participant_name}</span>}
                  </TableCell>
                  <TableCell className="font-medium text-white">{formatScore(r.final_score)}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{formatPercentile(r.percentile)}</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {rankings?.length === 0 && <p className="text-gray-500">No rankings yet.</p>}
    </div>
  );
}

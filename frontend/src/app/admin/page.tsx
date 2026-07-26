"use client";

import useSWR from "swr";
import Link from "next/link";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { adminApi } from "@/lib/api";
import { formatScore } from "@/lib/utils";

export default function AdminHomePage() {
  const { data: hackathons, isLoading } = useSWR("admin-hackathons", adminApi.hackathons, {
    refreshInterval: 20_000,
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Hackathons</h1>
          <p className="text-sm text-gray-400">All hackathons across EVALON.</p>
        </div>
        <Button asChild>
          <Link href="/admin/hackathons/new">
            <Plus className="mr-1 h-4 w-4" />
            New hackathon
          </Link>
        </Button>
      </div>

      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      )}

      {!isLoading && hackathons && hackathons.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-gray-400">
            No hackathons yet. Create your first one to get started.
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {hackathons?.map((h) => (
          <Link key={h.id} href={`/admin/hackathons/${h.id}`}>
            <Card className="h-full transition-colors hover:border-accent/40">
              <CardHeader className="flex flex-row items-start justify-between space-y-0">
                <CardTitle className="text-base">{h.title}</CardTitle>
                <Badge
                  variant={h.status === "active" ? "success" : h.status === "finalized" ? "default" : "secondary"}
                >
                  {h.status}
                </Badge>
              </CardHeader>
              <CardContent className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="text-xl font-bold text-white">{h.total_submissions}</div>
                  <div className="text-xs text-gray-500">Submissions</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-white">{h.evaluations_completed}</div>
                  <div className="text-xs text-gray-500">Completed</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-white">{formatScore(h.avg_score)}</div>
                  <div className="text-xs text-gray-500">Avg score</div>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { ArrowRight, LayoutDashboard, ListChecks, Rows3, Trophy, Columns3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { StatusBadge } from "@/components/hackathon/StatusBadge";
import { hackathonApi, dashboardApi, ApiError } from "@/lib/api";
import type { HackathonStatus } from "@/lib/types";

const NEXT_STATUS: Partial<Record<HackathonStatus, { target: HackathonStatus; label: string }>> = {
  draft: { target: "active", label: "Activate hackathon" },
  active: { target: "evaluating", label: "Move to evaluating" },
  evaluating: { target: "active", label: "Reopen for submissions" },
};

const QUICK_LINKS = [
  { href: "criteria", label: "Criteria", icon: ListChecks },
  { href: "submissions", label: "Submissions", icon: Rows3 },
  { href: "rankings", label: "Rankings", icon: Trophy },
  { href: "compare", label: "Compare", icon: Columns3 },
];

export default function HackathonOverviewPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const { data: hackathon, mutate } = useSWR(["hackathon", id], () => hackathonApi.get(id));
  const { data: stats } = useSWR(["dashboard", id], () => dashboardApi.get(id), { refreshInterval: 15_000 });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!hackathon) return <div className="text-gray-500">Loading...</div>;

  const transition = NEXT_STATUS[hackathon.status];
  const canFinalize =
    (hackathon.status === "active" || hackathon.status === "evaluating") &&
    !!stats &&
    stats.total_submissions > 0 &&
    stats.evaluations_in_progress === 0 &&
    stats.evaluations_queued === 0;

  const runTransition = async () => {
    if (!transition) return;
    setBusy(true);
    setError(null);
    try {
      await hackathonApi.updateStatus(id, transition.target);
      await mutate();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update status.");
    } finally {
      setBusy(false);
    }
  };

  const finalize = async () => {
    setBusy(true);
    setError(null);
    try {
      await hackathonApi.finalize(id);
      await mutate();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to finalize rankings.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white">{hackathon.title}</h1>
            <StatusBadge status={hackathon.status} />
          </div>
          {hackathon.description && <p className="max-w-xl text-sm text-gray-400">{hackathon.description}</p>}
        </div>
        <div className="flex gap-2">
          {transition && (
            <Button variant="outline" onClick={runTransition} disabled={busy}>
              {transition.label}
            </Button>
          )}
          {(hackathon.status === "active" || hackathon.status === "evaluating") && (
            <Button onClick={finalize} disabled={busy || !canFinalize} title={!canFinalize ? "All evaluations must complete first" : undefined}>
              Finalize rankings
            </Button>
          )}
        </div>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-5">
        {[
          { label: "Submissions", value: stats?.total_submissions },
          { label: "Completed", value: stats?.evaluations_completed },
          { label: "In progress", value: stats?.evaluations_in_progress },
          { label: "Queued", value: stats?.evaluations_queued },
          { label: "Failed", value: stats?.evaluations_failed },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="pt-6 text-center">
              <div className="text-3xl font-bold text-white">{s.value ?? "—"}</div>
              <div className="text-xs text-gray-500">{s.label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Link href={`/admin/dashboard?hackathon=${id}`}>
          <Card className="transition-colors hover:border-accent/40">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm">Live dashboard</CardTitle>
              <LayoutDashboard className="h-4 w-4 text-accent" />
            </CardHeader>
            <CardContent className="flex items-center text-sm text-gray-400">
              Real-time stats <ArrowRight className="ml-1 h-3 w-3" />
            </CardContent>
          </Card>
        </Link>
        {QUICK_LINKS.map((link) => (
          <Link key={link.href} href={`/admin/hackathons/${id}/${link.href}`}>
            <Card className="transition-colors hover:border-accent/40">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm">{link.label}</CardTitle>
                <link.icon className="h-4 w-4 text-accent" />
              </CardHeader>
              <CardContent className="flex items-center text-sm text-gray-400">
                View <ArrowRight className="ml-1 h-3 w-3" />
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

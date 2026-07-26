"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { hackathonApi, ApiError } from "@/lib/api";
import { getMySubmissionId, hasJoined, rememberJoined } from "@/lib/mySubmissions";
import { useAuthStore } from "@/store/auth";
import { useRouter } from "next/navigation";

export default function ParticipantHackathonsPage() {
  const router = useRouter();
  const userId = useAuthStore((s) => s.user?.id);
  const { data } = useSWR("hackathons-list", () => hackathonApi.list(1, 50));
  const [joinedSet, setJoinedSet] = useState<Set<string>>(new Set());
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (data) setJoinedSet(new Set(data.items.filter((h) => hasJoined(userId, h.id)).map((h) => h.id)));
  }, [data, userId]);

  const handleContinue = async (hackathonId: string) => {
    if (!userId) return;
    const existingSubmission = getMySubmissionId(userId, hackathonId);
    if (existingSubmission) {
      router.push(`/participant/evaluation/${existingSubmission}`);
      return;
    }
    setBusyId(hackathonId);
    try {
      await hackathonApi.join(hackathonId);
      rememberJoined(userId, hackathonId);
    } catch (err) {
      if (err instanceof ApiError && err.errorCode === "already_joined") {
        rememberJoined(userId, hackathonId);
      } else if (err instanceof ApiError) {
        setBusyId(null);
        return;
      }
    }
    router.push(`/participant/submit/${hackathonId}`);
  };

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-white">Hackathons</h1>
      {data?.items.length === 0 && <p className="text-gray-500">No active hackathons right now. Check back soon.</p>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data?.items.map((h) => {
          const joined = joinedSet.has(h.id) || !!getMySubmissionId(userId, h.id);
          const submissionId = getMySubmissionId(userId, h.id);
          return (
            <Card key={h.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{h.title}</CardTitle>
                  {joined && <Badge variant="success">Joined</Badge>}
                </div>
                {h.description && <CardDescription className="line-clamp-2">{h.description}</CardDescription>}
              </CardHeader>
              <CardContent>
                <Button
                  className="w-full"
                  disabled={busyId === h.id || h.status !== "active"}
                  onClick={() => handleContinue(h.id)}
                >
                  {h.status !== "active"
                    ? "Not accepting submissions"
                    : submissionId
                      ? "View my status"
                      : joined
                        ? "Submit your repo"
                        : "Join & submit"}
                </Button>
                {h.status === "finalized" && (
                  <Link
                    href={`/participant/leaderboard/${h.id}`}
                    className="mt-2 block text-center text-sm text-accent hover:underline"
                  >
                    View leaderboard →
                  </Link>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/auth";
import { getAllMySubmissions } from "@/lib/mySubmissions";

export default function ParticipantHomePage() {
  const user = useAuthStore((s) => s.user);
  const [mySubmissions, setMySubmissions] = useState<Record<string, string>>({});

  useEffect(() => {
    setMySubmissions(getAllMySubmissions(user?.id));
  }, [user?.id]);

  const submissionIds = Object.values(mySubmissions);

  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold text-white">Welcome{user?.full_name ? `, ${user.full_name}` : ""}</h1>
      <p className="mb-8 text-gray-400">Browse active hackathons, submit your repo, and track your evaluation.</p>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Get started</CardTitle>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link href="/participant/hackathons">
              Browse hackathons <ArrowRight className="ml-1 h-4 w-4" />
            </Link>
          </Button>
        </CardContent>
      </Card>

      {submissionIds.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Your submissions on this device</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {submissionIds.map((id) => (
              <Button key={id} asChild variant="outline" size="sm">
                <Link href={`/participant/evaluation/${id}`}>View submission {id.slice(0, 8)}...</Link>
              </Button>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

"use client";

import { useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { LiveDashboard } from "@/components/dashboard/LiveDashboard";
import { adminApi } from "@/lib/api";

export default function AdminDashboardPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const hackathonId = searchParams.get("hackathon");

  const { data: hackathons } = useSWR("admin-hackathons", adminApi.hackathons);
  const activeId = hackathonId || hackathons?.[0]?.id || null;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-white">Live dashboard</h1>
        {hackathons && hackathons.length > 0 && (
          <Select value={activeId ?? undefined} onValueChange={(value) => router.push(`/admin/dashboard?hackathon=${value}`)}>
            <SelectTrigger className="w-64">
              <SelectValue placeholder="Select a hackathon" />
            </SelectTrigger>
            <SelectContent>
              {hackathons.map((h) => (
                <SelectItem key={h.id} value={h.id}>
                  {h.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {!activeId && <p className="text-gray-500">Create a hackathon to see live stats here.</p>}
      {activeId && <LiveDashboard hackathonId={activeId} />}
    </div>
  );
}

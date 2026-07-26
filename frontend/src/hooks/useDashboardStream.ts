"use client";

import { useEffect, useState } from "react";
import { dashboardApi } from "@/lib/api";
import { streamSSE } from "@/lib/sse";
import { useAuthStore } from "@/store/auth";
import type { DashboardStats } from "@/lib/types";

export function useDashboardStream(hackathonId: string | null, initial: DashboardStats | null) {
  const token = useAuthStore((s) => s.accessToken);
  const [stats, setStats] = useState<DashboardStats | null>(initial);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (initial) setStats(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hackathonId]);

  useEffect(() => {
    if (!hackathonId || !token) return;
    const controller = new AbortController();
    let cancelled = false;

    const connect = () => {
      streamSSE(
        dashboardApi.streamUrl(hackathonId),
        token,
        (raw) => {
          setConnected(true);
          try {
            const parsed = JSON.parse(raw) as { event: string; data: DashboardStats };
            if (parsed.event === "stats_update") setStats(parsed.data);
          } catch {
            // ignore malformed frames
          }
        },
        controller.signal
      )
        .catch(() => undefined)
        .finally(() => {
          setConnected(false);
          // The stream is a long-lived 15s-interval connection; auto-reconnect
          // if it drops for any reason other than this hook unmounting.
          if (!cancelled) setTimeout(connect, 3000);
        });
    };
    connect();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [hackathonId, token]);

  return { stats, connected };
}

"use client";

import { useEffect, useState } from "react";
import { submissionApi } from "@/lib/api";
import { streamSSE } from "@/lib/sse";
import { useAuthStore } from "@/store/auth";
import type { SubmissionSSEEvent } from "@/lib/types";

const TERMINAL_EVENTS = new Set(["completed", "error"]);

export function useEvaluationStream(submissionId: string | null) {
  const token = useAuthStore((s) => s.accessToken);
  const [events, setEvents] = useState<SubmissionSSEEvent[]>([]);
  const [latest, setLatest] = useState<SubmissionSSEEvent | null>(null);
  const [terminal, setTerminal] = useState(false);
  const [connectionError, setConnectionError] = useState(false);

  useEffect(() => {
    if (!submissionId || !token) return;
    const controller = new AbortController();
    setEvents([]);
    setLatest(null);
    setTerminal(false);
    setConnectionError(false);

    streamSSE(
      submissionApi.statusStreamUrl(submissionId),
      token,
      (raw) => {
        try {
          const parsed = JSON.parse(raw) as SubmissionSSEEvent;
          setEvents((prev) => [...prev, parsed]);
          setLatest(parsed);
          if (TERMINAL_EVENTS.has(parsed.event)) setTerminal(true);
        } catch {
          // ignore malformed frames
        }
      },
      controller.signal
    ).catch((err) => {
      if (err.name !== "AbortError") setConnectionError(true);
    });

    return () => controller.abort();
  }, [submissionId, token]);

  return { events, latest, terminal, connectionError };
}

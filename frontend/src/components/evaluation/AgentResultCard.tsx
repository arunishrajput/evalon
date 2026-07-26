"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EvidenceList } from "./EvidenceList";
import { AgentAbstainedBadge } from "@/components/states/AgentAbstainedBadge";
import { formatScore, scoreColor } from "@/lib/utils";
import type { AgentResultDetail } from "@/lib/types";

const AGENT_LABELS: Record<string, string> = {
  repo_understanding: "Repository Understanding",
  code_quality: "Code Quality",
  innovation: "Innovation",
  comparative: "Comparative Intelligence",
};

export function AgentResultCard({ result }: { result: AgentResultDetail }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">{AGENT_LABELS[result.agent_id] || result.agent_id}</CardTitle>
        <span className={`text-2xl font-bold ${scoreColor(result.score_raw)}`}>{formatScore(result.score_raw)}</span>
      </CardHeader>
      <CardContent className="space-y-4">
        {result.abstained && <AgentAbstainedBadge />}

        {result.strengths.length > 0 && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-emerald-400">Strengths</h4>
            <ul className="space-y-1 text-sm text-gray-300">
              {result.strengths.map((s, i) => (
                <li key={i}>• {s}</li>
              ))}
            </ul>
          </div>
        )}

        {result.weaknesses.length > 0 && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-degraded">Weaknesses</h4>
            <ul className="space-y-1 text-sm text-gray-300">
              {result.weaknesses.map((w, i) => (
                <li key={i}>• {w}</li>
              ))}
            </ul>
          </div>
        )}

        {result.evidence.length > 0 && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Evidence</h4>
            <EvidenceList evidence={result.evidence} />
          </div>
        )}

        {result.reasoning && (
          <div>
            <button
              onClick={() => setExpanded((prev) => !prev)}
              className="flex items-center gap-1 text-xs font-medium text-accent hover:underline"
            >
              {expanded ? "Hide" : "Show"} full AI reasoning
              {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            </button>
            {expanded && (
              <p className="mt-2 whitespace-pre-wrap rounded-md bg-white/5 p-3 text-sm leading-relaxed text-gray-300">
                {result.reasoning}
              </p>
            )}
          </div>
        )}

        {result.fallback_used && !result.abstained && (
          <Badge variant="degraded">Fallback scoring used for part of this evaluation</Badge>
        )}
      </CardContent>
    </Card>
  );
}

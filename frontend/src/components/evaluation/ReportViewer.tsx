"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AgentResultCard } from "./AgentResultCard";
import type { EvaluationReport } from "@/lib/types";

function findAgent(report: EvaluationReport, agentId: string) {
  return report.agent_results.find((a) => a.agent_id === agentId);
}

export function ReportViewer({ report }: { report: EvaluationReport }) {
  return (
    <Tabs defaultValue="overview">
      <TabsList className="flex w-full flex-wrap gap-1">
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="code_quality">Code Quality</TabsTrigger>
        <TabsTrigger value="innovation">Innovation</TabsTrigger>
        <TabsTrigger value="architecture">Architecture</TabsTrigger>
        <TabsTrigger value="recommendations">Recommendations</TabsTrigger>
      </TabsList>

      <TabsContent value="overview" className="space-y-6">
        <Card>
          <CardContent className="pt-6">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Summary</p>
            <p className="text-gray-200">{report.summary}</p>
            {report.overall_assessment && (
              <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-gray-400">{report.overall_assessment}</p>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <CardContent className="pt-6">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-emerald-400">Top strengths</h4>
              <ul className="space-y-1 text-sm text-gray-300">
                {report.strengths.slice(0, 6).map((s, i) => (
                  <li key={i}>• {s}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-degraded">Top weaknesses</h4>
              <ul className="space-y-1 text-sm text-gray-300">
                {report.weaknesses.slice(0, 6).map((w, i) => (
                  <li key={i}>• {w}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      </TabsContent>

      <TabsContent value="code_quality">
        {findAgent(report, "code_quality") ? (
          <AgentResultCard result={findAgent(report, "code_quality")!} />
        ) : (
          <p className="text-gray-500">No code quality result available.</p>
        )}
      </TabsContent>

      <TabsContent value="innovation">
        {findAgent(report, "innovation") ? (
          <AgentResultCard result={findAgent(report, "innovation")!} />
        ) : (
          <p className="text-gray-500">No innovation result available.</p>
        )}
      </TabsContent>

      <TabsContent value="architecture" className="space-y-4">
        <Card>
          <CardContent className="pt-6">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Architecture notes</p>
            <p className="text-gray-200">{report.architecture_notes}</p>
            <p className="mt-2 text-xs text-gray-500">Project type: {report.project_type}</p>
          </CardContent>
        </Card>
        {findAgent(report, "repo_understanding") && <AgentResultCard result={findAgent(report, "repo_understanding")!} />}
      </TabsContent>

      <TabsContent value="recommendations" className="space-y-3">
        {report.recommendations.length === 0 && <p className="text-gray-500">No recommendations recorded.</p>}
        {report.recommendations.map((rec, i) => (
          <Card key={i}>
            <CardContent className="flex items-start gap-3 pt-6">
              <Badge
                variant={rec.priority === "high" ? "error" : rec.priority === "medium" ? "degraded" : "secondary"}
                className="mt-0.5 shrink-0"
              >
                {rec.priority}
              </Badge>
              <div>
                <p className="text-gray-200">{rec.recommendation}</p>
                <p className="mt-1 text-xs text-gray-500">{rec.rationale}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </TabsContent>
    </Tabs>
  );
}

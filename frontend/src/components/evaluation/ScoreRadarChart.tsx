"use client";

import { Legend, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip } from "recharts";
import type { AgentResultDetail, ComparativeReport, CriterionScoreEntry } from "@/lib/types";

interface RadarDatum {
  criterion: string;
  score: number;
  average?: number;
  agentId?: string;
}

function buildRadarData(byCriterion: CriterionScoreEntry[], comparative: ComparativeReport | null): RadarDatum[] {
  const averages = new Map<string, number>();
  if (comparative?.sufficient_data) {
    for (const c of comparative.criterion_comparisons as { criterion: string; pool_average: number }[]) {
      averages.set(c.criterion, c.pool_average);
    }
  }
  return byCriterion.map((c) => ({
    criterion: c.criterion,
    score: c.score,
    average: averages.get(c.criterion),
    agentId: c.agent_id ?? undefined,
  }));
}

interface ScoreRadarChartProps {
  byCriterion: CriterionScoreEntry[];
  comparative: ComparativeReport | null;
  onAxisClick?: (criterion: string, agentId?: string) => void;
}

export function ScoreRadarChart({ byCriterion, comparative, onAxisClick }: ScoreRadarChartProps) {
  const data = buildRadarData(byCriterion, comparative);
  const hasAverage = data.some((d) => d.average !== undefined);

  if (data.length === 0) {
    return <p className="py-12 text-center text-gray-500">No criterion scores available.</p>;
  }

  return (
    <div className="mx-auto w-full max-w-[600px]">
      <ResponsiveContainer width="100%" height={360}>
        <RadarChart data={data} outerRadius="70%">
          <PolarGrid stroke="#333" />
          <PolarAngleAxis
            dataKey="criterion"
            tick={(props) => <ClickableAxisTick {...props} onClick={onAxisClick} data={data} />}
          />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: "#666", fontSize: 10 }} />
          <Radar
            name="Your score"
            dataKey="score"
            stroke="#3b82f6"
            fill="#3b82f6"
            fillOpacity={0.25}
            strokeWidth={2}
            isAnimationActive
            animationDuration={600}
          />
          {hasAverage && (
            <Radar
              name="Hackathon average"
              dataKey="average"
              stroke="#f59e0b"
              fill="#f59e0b"
              fillOpacity={0.1}
              strokeWidth={1}
              strokeDasharray="4 4"
              isAnimationActive
              animationDuration={600}
            />
          )}
          <Legend wrapperStyle={{ fontSize: 12, color: "#9ca3af" }} />
          <Tooltip
            contentStyle={{ background: "#1a1a1a", border: "1px solid #333", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "#e5e7eb" }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

// Recharts passes raw SVG tick props here; we intercept the label render to
// make each axis clickable (spec: "Clickable axes → trigger ScoreTooltip popover").
function ClickableAxisTick(props: {
  x?: number;
  y?: number;
  payload?: { value: string };
  data: RadarDatum[];
  onClick?: (criterion: string, agentId?: string) => void;
}) {
  const { x, y, payload, data, onClick } = props;
  if (!payload) return null;
  const datum = data.find((d) => d.criterion === payload.value);
  return (
    <text
      x={x}
      y={y}
      textAnchor="middle"
      fontSize={12}
      fill="#9ca3af"
      className={onClick ? "cursor-pointer hover:fill-accent" : undefined}
      onClick={() => datum && onClick?.(datum.criterion, datum.agentId)}
    >
      {payload.value}
    </text>
  );
}

export function findAgentResult(agentResults: AgentResultDetail[], agentId?: string): AgentResultDetail | undefined {
  return agentId ? agentResults.find((a) => a.agent_id === agentId) : undefined;
}

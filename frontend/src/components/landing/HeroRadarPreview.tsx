"use client";

// The landing page's signature element: a live preview of the actual
// evaluation page's most important component (spec Section 10 calls the
// dual-overlay radar chart "the most visually impressive element" — it's
// EVALON's real product, not a marketing illustration of it). Same
// Recharts config as ScoreRadarChart.tsx, same colors, sample data.

import { useEffect, useState } from "react";
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from "recharts";

const SAMPLE_DATA = [
  { criterion: "Code Quality", score: 82, average: 61 },
  { criterion: "Innovation", score: 91, average: 58 },
  { criterion: "Understanding", score: 79, average: 65 },
];

const EVIDENCE = ["0 functions exceed the complexity threshold", "86% docstring coverage across core modules"];

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const listener = (e: MediaQueryListEvent) => setReduced(e.matches);
    query.addEventListener("change", listener);
    return () => query.removeEventListener("change", listener);
  }, []);
  return reduced;
}

export function HeroRadarPreview() {
  const [emphasize, setEmphasize] = useState(false);
  const reducedMotion = usePrefersReducedMotion();

  return (
    <div className="relative w-full max-w-md">
      <div className="rounded-2xl border border-white/10 bg-card/60 p-4 backdrop-blur">
        <div className="mb-1 flex items-center justify-between px-2 pt-1">
          <span className="font-mono text-[11px] uppercase tracking-wider text-gray-500">Sample evaluation</span>
          <span className="font-mono text-[11px] text-gray-600">n = 47 submissions</span>
        </div>
        {/* Sits above the chart, not below — the evidence callout overlaps
            the card's bottom-right corner, so a legend row down there
            would end up hidden underneath it. */}
        <div className="mb-1 flex flex-wrap items-center gap-x-4 gap-y-1 px-2 font-mono text-[10px] text-gray-400">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 shrink-0 rounded-sm bg-accent" aria-hidden />
            Your score
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 shrink-0 rounded-sm bg-degraded" aria-hidden />
            Hackathon average
          </span>
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <RadarChart data={SAMPLE_DATA} outerRadius="68%">
            <PolarGrid stroke="#2a2a2a" />
            <PolarAngleAxis
              dataKey="criterion"
              tick={(props) => <AxisTick {...props} onEnter={() => setEmphasize(true)} onLeave={() => setEmphasize(false)} />}
            />
            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: "#525252", fontSize: 9 }} tickCount={3} />
            <Radar
              name="Your score"
              dataKey="score"
              stroke="#3b82f6"
              fill="#3b82f6"
              fillOpacity={0.25}
              strokeWidth={2}
              isAnimationActive={!reducedMotion}
              animationDuration={900}
              animationEasing="ease-out"
            />
            <Radar
              name="Hackathon average"
              dataKey="average"
              stroke="#f59e0b"
              fill="#f59e0b"
              fillOpacity={0.08}
              strokeWidth={1}
              strokeDasharray="4 4"
              isAnimationActive={!reducedMotion}
              animationDuration={900}
              animationEasing="ease-out"
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* The actual "why this score?" popover from ScoreTooltip, shown
          permanently here rather than hover-gated — a landing visitor
          can't hover a chart axis they don't yet know is interactive, so
          the affordance itself is the point. Hovering "Code Quality" on
          the chart above only adds a subtle emphasis ring, it never
          toggles visibility — that would fail on touch devices. */}
      <div
        className={`absolute -bottom-6 -right-4 w-56 rounded-lg border p-3 shadow-xl transition-[box-shadow,border-color] duration-300 sm:-right-8 motion-safe:animate-fade-up motion-safe:[animation-delay:700ms] ${
          emphasize ? "border-accent/50 shadow-accent/10" : "border-white/10"
        } bg-card-elevated`}
      >
        <div className="mb-1.5 flex items-baseline justify-between">
          <span className="text-xs font-semibold text-white">Code Quality</span>
          <span className="font-mono text-sm font-bold text-accent">82</span>
        </div>
        <ul className="space-y-1 text-[11px] leading-snug text-gray-400">
          {EVIDENCE.map((item) => (
            <li key={item} className="flex gap-1.5">
              <span className="text-accent">•</span>
              {item}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function AxisTick(props: {
  x?: number;
  y?: number;
  payload?: { value: string };
  onEnter: () => void;
  onLeave: () => void;
}) {
  const { x, y, payload, onEnter, onLeave } = props;
  if (!payload) return null;
  const isCodeQuality = payload.value === "Code Quality";
  return (
    <text
      x={x}
      y={y}
      textAnchor="middle"
      fontFamily="var(--font-mono)"
      fontSize={11}
      fill={isCodeQuality ? "#3b82f6" : "#9ca3af"}
      className={isCodeQuality ? "cursor-pointer" : undefined}
      onMouseEnter={isCodeQuality ? onEnter : undefined}
      onMouseLeave={isCodeQuality ? onLeave : undefined}
    >
      {payload.value}
    </text>
  );
}

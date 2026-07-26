"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const BUCKET_ORDER = ["0-10", "10-20", "20-30", "30-40", "40-50", "50-60", "60-70", "70-80", "80-90", "90-100"];

export function ScoreHistogram({ distribution }: { distribution: Record<string, number> }) {
  const data = BUCKET_ORDER.map((bucket) => ({ bucket, count: distribution[bucket] || 0 }));

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#262626" vertical={false} />
        <XAxis dataKey="bucket" tick={{ fill: "#9ca3af", fontSize: 10 }} interval={1} />
        <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} allowDecimals={false} />
        <Tooltip
          contentStyle={{ background: "#1a1a1a", border: "1px solid #333", borderRadius: 8, fontSize: 12 }}
          labelStyle={{ color: "#e5e7eb" }}
          cursor={{ fill: "rgba(59,130,246,0.08)" }}
        />
        <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} isAnimationActive animationDuration={400} />
      </BarChart>
    </ResponsiveContainer>
  );
}

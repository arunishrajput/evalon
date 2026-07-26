"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function TechStackCloud({ frequency }: { frequency: Record<string, number> }) {
  const data = Object.entries(frequency)
    .map(([tech, count]) => ({ tech, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);

  if (data.length === 0) {
    return <p className="flex h-[240px] items-center justify-center text-sm text-gray-500">No tech stack data yet.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#262626" horizontal={false} />
        <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 11 }} allowDecimals={false} />
        <YAxis type="category" dataKey="tech" width={90} tick={{ fill: "#9ca3af", fontSize: 11 }} />
        <Tooltip
          contentStyle={{ background: "#1a1a1a", border: "1px solid #333", borderRadius: 8, fontSize: 12 }}
          labelStyle={{ color: "#e5e7eb" }}
          cursor={{ fill: "rgba(59,130,246,0.08)" }}
        />
        <Bar dataKey="count" fill="#f59e0b" radius={[0, 4, 4, 0]} isAnimationActive animationDuration={400} />
      </BarChart>
    </ResponsiveContainer>
  );
}

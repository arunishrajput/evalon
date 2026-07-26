import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatScore(score: number | string | null | undefined): string {
  if (score === null || score === undefined) return "—";
  const n = typeof score === "string" ? parseFloat(score) : score;
  if (Number.isNaN(n)) return "—";
  return n.toFixed(1);
}

export function scoreColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return "text-gray-400";
  if (score >= 80) return "text-emerald-400";
  if (score >= 60) return "text-accent";
  if (score >= 40) return "text-degraded";
  return "text-error";
}

export function formatPercentile(percentile: number | string | null | undefined): string {
  if (percentile === null || percentile === undefined) return "—";
  const n = typeof percentile === "string" ? parseFloat(percentile) : percentile;
  if (Number.isNaN(n)) return "—";
  return `Top ${(100 - n).toFixed(0)}%`;
}

export function formatDuration(startIso: string | null, endIso: string | null): string {
  if (!startIso || !endIso) return "";
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
  if (ms <= 0) return "";
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

export function initials(name: string | null | undefined): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

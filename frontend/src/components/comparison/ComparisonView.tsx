"use client";

import { Trophy } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { formatScore, formatPercentile } from "@/lib/utils";
import type { ComparisonSubmission } from "@/lib/types";

function normalize(text: string): string {
  return text.trim().toLowerCase();
}

/** A strength is "yours alone" (highlight green) if no other compared
 * submission lists the same strength. A weakness is a "shared pain point"
 * (highlight red) if at least half the OTHER submissions share it — per
 * spec Section 10's ComparisonView.tsx contract. */
function classify(
  submissions: ComparisonSubmission[],
  index: number,
  field: "strengths" | "weaknesses",
  item: string
): "unique-strength" | "shared-weakness" | null {
  const others = submissions.filter((_, i) => i !== index);
  const sharedCount = others.filter((s) => s[field].some((x) => normalize(x) === normalize(item))).length;

  if (field === "strengths" && sharedCount === 0) return "unique-strength";
  if (field === "weaknesses" && others.length > 0 && sharedCount / others.length >= 0.5) return "shared-weakness";
  return null;
}

export function ComparisonView({ submissions }: { submissions: ComparisonSubmission[] }) {
  if (submissions.length === 0) {
    return <p className="text-gray-500">No evaluated submissions selected.</p>;
  }

  const allCriteria = Array.from(new Set(submissions.flatMap((s) => s.scores_by_criterion.map((c) => c.criterion))));

  return (
    <div className="overflow-x-auto pb-4" id="comparison-view">
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: `repeat(${submissions.length}, minmax(280px, 1fr))` }}
      >
        {submissions.map((submission, index) => (
          <div key={submission.submission_id} className="flex flex-col rounded-lg border border-white/10 bg-card">
            {/* Not `sticky`: with a page-level (vertical) scrolling ancestor rather
                than a dedicated horizontal-only scroll container, `position: sticky`
                here stuck the header at a fixed viewport offset that overlapped and
                fully hid the content below it once the page scrolled — confirmed via
                getBoundingClientRect (header bottom > content top). A plain header
                avoids that; sacrifices staying pinned while scrolling a single very
                tall card, which matters less than the content being visible at all. */}
            <div className="rounded-t-lg border-b border-white/10 bg-card-elevated p-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-white">{submission.repo_name || "Untitled"}</h3>
                {submission.rank && (
                  <Badge variant="default" className="gap-1">
                    <Trophy className="h-3 w-3" />#{submission.rank}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-gray-500">{submission.participant_name}</p>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-white">{formatScore(submission.final_score)}</span>
                {submission.percentile !== null && (
                  <span className="text-xs text-gray-400">{formatPercentile(submission.percentile)}</span>
                )}
              </div>
            </div>

            <div className="space-y-4 p-4">
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Scores by criterion</h4>
                <div className="space-y-2">
                  {allCriteria.map((criterionName) => {
                    const entry = submission.scores_by_criterion.find((c) => c.criterion === criterionName);
                    return (
                      <div key={criterionName}>
                        <div className="mb-0.5 flex justify-between text-xs">
                          <span className="text-gray-400">{criterionName}</span>
                          <span className="text-gray-300">{entry ? formatScore(entry.score) : "—"}</span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-white/10">
                          <div
                            className="h-full rounded-full bg-accent"
                            style={{ width: `${entry ? Math.min(entry.score, 100) : 0}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Tech stack</h4>
                <div className="flex flex-wrap gap-1">
                  {submission.tech_stack.length === 0 && <span className="text-xs text-gray-600">Unknown</span>}
                  {submission.tech_stack.map((tech) => (
                    <Badge key={tech} variant="secondary">
                      {tech}
                    </Badge>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Top strengths</h4>
                <ul className="space-y-1 text-sm">
                  {submission.strengths.slice(0, 4).map((strength, i) => {
                    const flag = classify(submissions, index, "strengths", strength);
                    return (
                      <li
                        key={i}
                        className={
                          flag === "unique-strength"
                            ? "rounded bg-emerald-500/10 px-2 py-1 text-emerald-300"
                            : "px-2 py-1 text-gray-300"
                        }
                      >
                        • {strength}
                      </li>
                    );
                  })}
                  {submission.strengths.length === 0 && <li className="px-2 text-gray-600">None recorded</li>}
                </ul>
              </div>

              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Top weaknesses</h4>
                <ul className="space-y-1 text-sm">
                  {submission.weaknesses.slice(0, 4).map((weakness, i) => {
                    const flag = classify(submissions, index, "weaknesses", weakness);
                    return (
                      <li
                        key={i}
                        className={
                          flag === "shared-weakness"
                            ? "rounded bg-error/10 px-2 py-1 text-red-300"
                            : "px-2 py-1 text-gray-300"
                        }
                      >
                        • {weakness}
                      </li>
                    );
                  })}
                  {submission.weaknesses.length === 0 && <li className="px-2 text-gray-600">None recorded</li>}
                </ul>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

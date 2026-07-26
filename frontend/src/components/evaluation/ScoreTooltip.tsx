"use client";

import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { formatScore } from "@/lib/utils";

interface ScoreTooltipProps {
  children: React.ReactNode;
  criterion: string;
  score: number;
  topEvidence: string[];
  onViewFull?: () => void;
}

/** shadcn/ui Popover, open on hover (desktop) and click (everywhere) — the
 * spec's "Why This Score?" explainability affordance (Section 10). */
export function ScoreTooltip({ children, criterion, score, topEvidence, onViewFull }: ScoreTooltipProps) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="cursor-pointer text-left"
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
          onClick={() => setOpen((prev) => !prev)}
        >
          {children}
        </button>
      </PopoverTrigger>
      <PopoverContent onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
        <div className="mb-2 flex items-baseline justify-between">
          <h4 className="font-semibold text-white">{criterion}</h4>
          <span className="text-lg font-bold text-accent">{formatScore(score)} / 100</span>
        </div>
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">
          Top findings that drove this score
        </p>
        {topEvidence.length === 0 ? (
          <p className="text-sm text-gray-500">No evidence recorded for this criterion.</p>
        ) : (
          <ul className="mb-3 space-y-1.5 text-sm text-gray-300">
            {topEvidence.slice(0, 2).map((item, i) => (
              <li key={i} className="flex gap-1.5">
                <span className="text-accent">•</span>
                {item}
              </li>
            ))}
          </ul>
        )}
        {onViewFull && (
          <button
            onClick={onViewFull}
            className="flex items-center gap-1 text-xs font-medium text-accent hover:underline"
          >
            View full analysis <ArrowRight className="h-3 w-3" />
          </button>
        )}
      </PopoverContent>
    </Popover>
  );
}

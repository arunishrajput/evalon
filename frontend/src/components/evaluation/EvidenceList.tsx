import { Badge } from "@/components/ui/badge";
import type { EvidenceItem } from "@/lib/types";

const IMPACT_VARIANT: Record<string, "success" | "degraded" | "error" | "secondary"> = {
  positive: "success",
  neutral: "secondary",
  negative: "error",
  high: "error",
  medium: "degraded",
  low: "secondary",
};

export function EvidenceList({ evidence }: { evidence: EvidenceItem[] }) {
  if (evidence.length === 0) {
    return <p className="text-sm text-gray-500">No detailed evidence recorded.</p>;
  }
  return (
    <ul className="space-y-2">
      {evidence.map((item, i) => (
        <li key={i} className="flex items-start gap-2 rounded-md bg-white/5 px-3 py-2 text-sm">
          {item.impact && (
            <Badge variant={IMPACT_VARIANT[String(item.impact).toLowerCase()] || "secondary"} className="mt-0.5 shrink-0">
              {String(item.impact)}
            </Badge>
          )}
          <div>
            <p className="text-gray-200">{item.description}</p>
            {item.source && <p className="mt-0.5 text-xs text-gray-500">{item.source}</p>}
          </div>
        </li>
      ))}
    </ul>
  );
}

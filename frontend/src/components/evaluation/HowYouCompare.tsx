import { Star, TrendingUp, Trophy, Users } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ComparativeReport } from "@/lib/types";

export function HowYouCompare({ comparative }: { comparative: ComparativeReport | null }) {
  if (!comparative || !comparative.sufficient_data) {
    return (
      <Card className="border-dashed bg-card-elevated/50">
        <CardContent className="py-8 text-center text-sm text-gray-500">
          {comparative?.data_note || "Comparative data will be available once more teams complete evaluation."}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardContent className="flex flex-col items-center gap-1 py-5 text-center">
            <Trophy className="h-4 w-4 text-accent" />
            <div className="text-xl font-bold text-white">#{comparative.rank_in_pool}</div>
            <div className="text-xs text-gray-500">of {comparative.total_submissions_in_pool} subs</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex flex-col items-center gap-1 py-5 text-center">
            <TrendingUp className="h-4 w-4 text-accent" />
            <div className="text-xl font-bold text-white">{comparative.percentile_label}</div>
            <div className="text-xs text-gray-500">Percentile</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex flex-col items-center gap-1 py-5 text-center">
            <Users className="h-4 w-4 text-accent" />
            <div className="text-xl font-bold text-white">{comparative.score_vs_average}</div>
            <div className="text-xs text-gray-500">vs average</div>
          </CardContent>
        </Card>
      </div>

      {(comparative.shared_tech_stacks.length > 0 || comparative.unique_tech_stacks.length > 0) && (
        <div className="flex flex-wrap gap-2">
          {comparative.shared_tech_stacks.map((t, i) => (
            <Badge key={`shared-${i}`} variant="secondary">
              {(t as { message?: string }).message || JSON.stringify(t)}
            </Badge>
          ))}
          {comparative.unique_tech_stacks.map((t, i) => (
            <Badge key={`unique-${i}`} variant="success" className="gap-1">
              <Star className="h-3 w-3" />
              {(t as { message?: string }).message || JSON.stringify(t)}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

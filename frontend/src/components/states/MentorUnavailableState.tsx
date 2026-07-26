import { Sparkles } from "lucide-react";

export function MentorUnavailableState({ reason }: { reason?: string | null }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-white/10 bg-card-elevated px-6 py-12 text-center">
      <Sparkles className="h-8 w-8 text-gray-500" />
      <p className="max-w-sm text-sm text-gray-400">
        {reason || "Your mentor is being prepared. Check back soon."}
      </p>
    </div>
  );
}

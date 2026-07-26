import { Loader2 } from "lucide-react";

export function ModelLoadingState({ message }: { message?: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-accent/20 bg-accent/5 px-4 py-3 text-sm text-gray-200">
      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-accent" />
      <span>{message || "AI is finishing another evaluation. You're next in queue..."}</span>
    </div>
  );
}

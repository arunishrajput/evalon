import { AlertTriangle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export function DegradedBanner({ message }: { message?: string | null }) {
  return (
    <Alert variant="degraded" className="flex items-start gap-3">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-degraded" />
      <div>
        <AlertTitle>Partial evaluation</AlertTitle>
        <AlertDescription>
          {message ||
            "Some AI agents used fallback scoring. Results are based primarily on static analysis and may be less nuanced. Full AI evaluation was not possible at this time."}
        </AlertDescription>
      </div>
    </Alert>
  );
}

import { CircleSlash } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function AgentAbstainedBadge() {
  return (
    <Badge variant="degraded" className="gap-1">
      <CircleSlash className="h-3 w-3" />
      This agent used static analysis only
    </Badge>
  );
}

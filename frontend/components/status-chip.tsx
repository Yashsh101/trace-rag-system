import { Badge } from "@/components/ui/badge";
import { classForStatus, cn } from "@/lib/utils";

export function StatusChip({ status }: { status: string }) {
  return <Badge className={cn("capitalize", classForStatus(status))}>{status.replace("_", " ")}</Badge>;
}

import { ArrowUpRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function MetricCard({
  label,
  value,
  detail,
  tone = "neutral"
}: {
  label: string;
  value: string | number;
  detail: string;
  tone?: "neutral" | "good" | "warn" | "bad";
}) {
  const tones = {
    neutral: "text-zinc-300",
    good: "text-emerald-200",
    warn: "text-amber-200",
    bad: "text-red-200"
  };
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <div className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-500">{label}</div>
          <ArrowUpRight className="h-4 w-4 text-zinc-600" />
        </div>
        <div className={cn("mt-4 text-3xl font-semibold tracking-tight", tones[tone])}>{value}</div>
        <div className="mt-2 text-sm text-zinc-500">{detail}</div>
      </CardContent>
    </Card>
  );
}

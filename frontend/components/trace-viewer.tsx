"use client";

import { CheckCircle2, Clock3, Cpu, FileText, Hash, ShieldAlert } from "lucide-react";
import type { QueryTrace } from "@/lib/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { formatCost, formatMs } from "@/lib/utils";
import { StatusChip } from "@/components/status-chip";

export function TraceViewer({ trace }: { trace: QueryTrace | null }) {
  if (!trace) {
    return (
      <Card className="border-dashed">
        <CardContent className="flex min-h-80 flex-col items-center justify-center p-8 text-center">
          <Cpu className="h-8 w-8 text-zinc-600" />
          <div className="mt-4 text-sm font-medium text-zinc-200">No trace selected</div>
          <div className="mt-2 max-w-sm text-sm leading-6 text-zinc-500">Run a query or open a recent trace to inspect retrieval, validation, and model metadata.</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle>Trace {trace.query_log_id}</CardTitle>
              <CardDescription className="mt-1">Trace ID {trace.trace_id}</CardDescription>
            </div>
            <StatusChip status={trace.status} />
          </div>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Meta icon={Clock3} label="Query" value={formatMs(trace.metrics.query_latency_ms)} />
          <Meta icon={Cpu} label="Retrieval" value={formatMs(trace.metrics.retrieval_latency_ms)} />
          <Meta icon={Cpu} label="LLM" value={formatMs(trace.metrics.llm_latency_ms)} />
          <Meta icon={CheckCircle2} label="Cost" value={formatCost(trace.metrics.estimated_cost)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Validation</CardTitle>
          <CardDescription>Grounding checks, no-answer classification, and ACL denial counts.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Badge>{String(trace.validation_result.reason ?? "unknown")}</Badge>
            <Badge>support {String(trace.validation_result.support_ok ?? "n/a")}</Badge>
            <Badge>denied {trace.denied_retrieval_count}</Badge>
            <Badge>{trace.auth.user_id ?? "anonymous"}</Badge>
          </div>
          <Separator />
          <div className="grid gap-3 sm:grid-cols-3">
            <Meta icon={Cpu} label="Model" value={trace.model_usage.model} />
            <Meta icon={Hash} label="Tokens" value={String(trace.model_usage.total_tokens ?? 0)} />
            <Meta icon={ShieldAlert} label="No answer" value={String(trace.metrics.no_answer ?? false)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Retrieved Chunks</CardTitle>
          <CardDescription>Ranked evidence sent toward answer generation.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {trace.retrieved_chunks.length === 0 ? (
            <div className="rounded-md border border-white/10 bg-white/5 p-6 text-center text-sm text-zinc-500">No chunks retrieved.</div>
          ) : (
            trace.retrieved_chunks.map((chunk) => (
              <div key={chunk.chunk_id} className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <FileText className="h-4 w-4 shrink-0 text-cyan-200" />
                    <span className="truncate text-sm font-medium text-white">{chunk.filename}</span>
                  </div>
                  <div className="flex gap-2">
                    <Badge>score {chunk.score.toFixed(4)}</Badge>
                    <Badge>{chunk.source}</Badge>
                  </div>
                </div>
                <p className="mt-3 text-sm leading-6 text-zinc-300">{chunk.snippet}</p>
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-zinc-500">
                  <span>chunk {chunk.chunk_id}</span>
                  <span>document {chunk.document_id}</span>
                  <span>page {chunk.page_start ?? "n/a"}</span>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Meta({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-zinc-500">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="mt-2 truncate text-sm font-medium text-zinc-100">{value}</div>
    </div>
  );
}

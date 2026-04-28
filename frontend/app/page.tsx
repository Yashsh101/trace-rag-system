"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, CircleAlert, FileText, Loader2, MessageSquare, RefreshCw } from "lucide-react";
import type { ReadinessResponse } from "@/lib/types";
import { useConsoleSettings } from "@/lib/settings";
import { useConsoleStore } from "@/lib/store";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { StatusChip } from "@/components/status-chip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/error-state";

export default function DashboardPage() {
  const { client } = useConsoleSettings();
  const { jobs, queries, evalSnapshot } = useConsoleStore();
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      setReadiness(await client.readiness());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load readiness.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const completed = jobs.filter((job) => job.status === "completed").length;
  const failed = jobs.filter((job) => job.status === "failed").length;
  const indexedChunks = jobs.reduce((sum, job) => sum + (job.status === "completed" ? job.chunk_count : 0), 0);
  const latestQueries = useMemo(() => queries.slice(0, 5), [queries]);

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="A control plane for health, indexing, retrieval quality, and the recent query trail."
        action={
          <Button variant="outline" onClick={refresh} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Refresh
          </Button>
        }
      />

      {error && <div className="mb-6"><ErrorState title="System check failed" message={error} /></div>}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="System" value={readiness?.status ?? "checking"} detail="FastAPI readiness state" tone={readiness?.ready ? "good" : "warn"} />
        <MetricCard label="Documents indexed" value={completed} detail={`${indexedChunks} chunks in local session`} tone="neutral" />
        <MetricCard label="Completed jobs" value={completed} detail={`${failed} failed ingestion jobs`} tone={failed ? "bad" : "good"} />
        <MetricCard label="Recent queries" value={queries.length} detail="Captured in this browser session" tone="neutral" />
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>System Status</CardTitle>
            <CardDescription>Readiness checks from the backend.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading && !readiness ? (
              <>
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
              </>
            ) : (
              Object.entries(readiness?.checks ?? {}).map(([key, check]) => (
                <div key={key} className="flex items-center justify-between rounded-md border border-white/10 bg-white/[0.03] p-3">
                  <div className="flex items-center gap-3">
                    {check.ok ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : <CircleAlert className="h-4 w-4 text-red-300" />}
                    <div>
                      <div className="text-sm font-medium capitalize text-white">{key}</div>
                      <div className="text-xs text-zinc-500">{check.error || check.reason || check.backend || check.environment || "operational"}</div>
                    </div>
                  </div>
                  <StatusChip status={check.ok ? "ok" : "failed"} />
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Eval Score Cards</CardTitle>
            <CardDescription>Last known eval summary.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3">
            {Object.entries(evalSnapshot)
              .filter(([key]) => key !== "updatedAt")
              .map(([key, value]) => (
                <div key={key} className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                  <div className="text-xs capitalize text-zinc-500">{key.replaceAll("_", " ")}</div>
                  <div className="mt-2 text-2xl font-semibold text-white">{Math.round(Number(value) * 100)}%</div>
                </div>
              ))}
          </CardContent>
        </Card>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Ingestion Jobs</CardTitle>
            <CardDescription>Most recent local upload jobs.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {jobs.length === 0 ? <Empty icon={FileText} text="No ingestion jobs captured yet." /> : jobs.slice(0, 6).map((job) => (
              <motion.div key={job.job_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center justify-between rounded-md border border-white/10 bg-white/[0.03] p-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-white">{job.filename}</div>
                  <div className="text-xs text-zinc-500">{job.chunk_count} chunks</div>
                </div>
                <StatusChip status={job.status} />
              </motion.div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Queries</CardTitle>
            <CardDescription>Answers, no-answer events, and trace IDs.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {latestQueries.length === 0 ? <Empty icon={MessageSquare} text="No queries sent from this console yet." /> : latestQueries.map((query) => (
              <div key={query.trace_id} className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-white">{query.question}</div>
                    <div className="mt-1 truncate text-xs text-zinc-500">{query.trace_id}</div>
                  </div>
                  <Badge>{query.no_answer ? "no answer" : "answered"}</Badge>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Empty({ icon: Icon, text }: { icon: React.ElementType; text: string }) {
  return (
    <div className="flex min-h-32 flex-col items-center justify-center rounded-md border border-dashed border-white/10 bg-white/[0.02] p-6 text-center text-sm text-zinc-500">
      <Icon className="mb-3 h-5 w-5" />
      {text}
    </div>
  );
}

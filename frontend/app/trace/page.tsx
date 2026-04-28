"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { RagApiError } from "@/lib/api";
import type { QueryTrace } from "@/lib/types";
import { useConsoleSettings } from "@/lib/settings";
import { useConsoleStore } from "@/lib/store";
import { PageHeader } from "@/components/page-header";
import { TraceViewer } from "@/components/trace-viewer";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export default function TracePage() {
  const { client } = useConsoleSettings();
  const { queries } = useConsoleStore();
  const [queryLogId, setQueryLogId] = useState("");
  const [trace, setTrace] = useState<QueryTrace | null>(queries.find((query) => query.trace)?.trace ?? null);
  const [error, setError] = useState<string | null>(null);

  const recentTraces = useMemo(() => queries.filter((query) => query.query_log_id).slice(0, 8), [queries]);

  useEffect(() => {
    if (!trace) {
      const latestTrace = queries.find((query) => query.trace)?.trace;
      if (latestTrace) setTrace(latestTrace);
    }
  }, [queries, trace]);

  const loadTrace = async (id: number) => {
    setError(null);
    try {
      setTrace(await client.trace(id));
    } catch (caught) {
      const message = caught instanceof RagApiError ? caught.message : caught instanceof Error ? caught.message : "Unable to load trace.";
      setError(message);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const id = Number(queryLogId);
    if (Number.isFinite(id) && id > 0) loadTrace(id);
  };

  return (
    <div>
      <PageHeader title="Source Trace Panel" description="Inspect retrieved chunks, citations, validation gates, model usage, and latency metadata." />
      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Open Trace</CardTitle>
              <CardDescription>Enter a query log ID from chat.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={submit} className="flex gap-2">
                <Input value={queryLogId} onChange={(event) => setQueryLogId(event.target.value)} inputMode="numeric" placeholder="Query log ID" />
                <Button type="submit" size="icon" title="Fetch trace">
                  <Search className="h-4 w-4" />
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent</CardTitle>
              <CardDescription>Traces from this browser session.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {recentTraces.length === 0 ? (
                <div className="rounded-md border border-dashed border-white/10 p-6 text-center text-sm text-zinc-500">No recent trace IDs.</div>
              ) : (
                recentTraces.map((query) => (
                  <button
                    key={query.trace_id}
                    type="button"
                    onClick={() => query.query_log_id && loadTrace(query.query_log_id)}
                    className="w-full rounded-md border border-white/10 bg-white/[0.03] p-3 text-left transition-colors hover:bg-white/[0.06]"
                  >
                    <div className="truncate text-sm font-medium text-white">{query.question}</div>
                    <div className="mt-2 flex gap-2">
                      <Badge>{query.query_log_id}</Badge>
                      <Badge>{query.no_answer ? "no answer" : "answered"}</Badge>
                    </div>
                  </button>
                ))
              )}
            </CardContent>
          </Card>

          {error && <ErrorState title="Trace unavailable" message={error} />}
        </div>
        <TraceViewer trace={trace} />
      </div>
    </div>
  );
}

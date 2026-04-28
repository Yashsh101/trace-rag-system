"use client";

import { Clock3, FileText } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { UploadDropzone } from "@/components/upload-dropzone";
import { useConsoleStore } from "@/lib/store";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusChip } from "@/components/status-chip";

export default function UploadPage() {
  const { jobs } = useConsoleStore();

  return (
    <div>
      <PageHeader title="Document Upload" description="Index PDFs with durable job tracking, state polling, and clear failure handling." />
      <div className="grid gap-6 xl:grid-cols-[1fr_420px]">
        <UploadDropzone />
        <Card>
          <CardHeader>
            <CardTitle>Job Lifecycle</CardTitle>
            <CardDescription>Queued, processing, completed, and failed states from the worker.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {jobs.length === 0 ? (
              <div className="flex min-h-64 flex-col items-center justify-center rounded-md border border-dashed border-white/10 text-center text-sm text-zinc-500">
                <Clock3 className="mb-3 h-5 w-5" />
                Upload a PDF to start tracking ingestion.
              </div>
            ) : (
              jobs.map((job) => (
                <div key={job.job_id} className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex min-w-0 items-center gap-2">
                        <FileText className="h-4 w-4 shrink-0 text-cyan-200" />
                        <span className="truncate text-sm font-medium text-white">{job.filename}</span>
                      </div>
                      <div className="mt-1 text-xs text-zinc-500">Job {job.job_id}</div>
                    </div>
                    <StatusChip status={job.status} />
                  </div>
                  <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
                    <Datum label="Chunks" value={String(job.chunk_count)} />
                    <Datum label="Document" value={String(job.document_id ?? "n/a")} />
                    <Datum label="Failed" value={job.failed_at ? "yes" : "no"} />
                  </div>
                  {job.error_message && <div className="mt-3 rounded-md border border-red-400/20 bg-red-950/20 p-3 text-sm text-red-100">{job.error_message}</div>}
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Datum({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-zinc-950 p-2">
      <div className="text-zinc-500">{label}</div>
      <div className="mt-1 truncate font-medium text-zinc-200">{value}</div>
    </div>
  );
}

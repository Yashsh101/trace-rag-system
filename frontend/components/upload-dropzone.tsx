"use client";

import { useCallback, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FileUp, Loader2, XCircle } from "lucide-react";
import { RagApiError } from "@/lib/api";
import type { StoredJob } from "@/lib/types";
import { useConsoleSettings } from "@/lib/settings";
import { useConsoleStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent } from "@/components/ui/card";
import { StatusChip } from "@/components/status-chip";
import { ErrorState } from "@/components/error-state";

export function UploadDropzone() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { client } = useConsoleSettings();
  const { jobs, upsertJob } = useConsoleStore();
  const activeJob = jobs.find((job) => job.job_id === activeJobId);

  const pollJob = useCallback(
    async (jobId: string, filename: string) => {
      for (let attempt = 0; attempt < 80; attempt += 1) {
        const job = await client.job(jobId);
        upsertJob({ ...job, filename });
        if (job.status === "completed" || job.status === "failed") return job;
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
      }
      throw new Error("Ingestion job timed out while polling.");
    },
    [client, upsertJob]
  );

  const upload = useCallback(
    async (file: File | undefined) => {
      if (!file) return;
      setError(null);
      setProgress(0);
      try {
        if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
          throw new Error("Only PDF files are supported.");
        }
        const response = await client.ingest(file, setProgress);
        const initial: StoredJob = {
          job_id: response.job_id,
          status: response.status,
          document_id: response.document_id || null,
          error_message: null,
          chunk_count: response.chunk_count,
          created_at: new Date().toISOString(),
          started_at: null,
          completed_at: null,
          failed_at: null,
          filename: response.filename
        };
        upsertJob(initial);
        setActiveJobId(response.job_id);
        await pollJob(response.job_id, response.filename);
      } catch (caught) {
        const message = caught instanceof RagApiError ? caught.message : caught instanceof Error ? caught.message : "Upload failed.";
        setError(message);
      }
    },
    [client, pollJob, upsertJob]
  );

  return (
    <div className="space-y-4">
      <input ref={inputRef} className="hidden" type="file" accept="application/pdf" onChange={(event) => upload(event.target.files?.[0])} />
      <motion.div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          upload(event.dataTransfer.files?.[0]);
        }}
        className="rounded-lg border border-dashed border-white/15 bg-zinc-950/70 p-8 text-center transition-colors data-[dragging=true]:border-cyan-300/60 data-[dragging=true]:bg-cyan-300/5"
        data-dragging={dragging}
      >
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-lg border border-cyan-300/20 bg-cyan-300/10">
          <FileUp className="h-6 w-6 text-cyan-200" />
        </div>
        <h2 className="mt-5 text-lg font-semibold text-white">Drop PDFs to index</h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-zinc-400">Upload source documents into your RAG pipeline and watch durable ingestion state in real time.</p>
        <Button className="mt-6" onClick={() => inputRef.current?.click()}>
          Select PDF
        </Button>
      </motion.div>

      <AnimatePresence>
        {progress > 0 && progress < 100 && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
            <Progress value={progress} />
          </motion.div>
        )}
      </AnimatePresence>

      {activeJob && (
        <Card>
          <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-sm font-medium text-white">{activeJob.filename}</div>
              <div className="mt-1 text-xs text-zinc-500">Job {activeJob.job_id}</div>
            </div>
            <div className="flex items-center gap-3">
              {activeJob.status === "processing" || activeJob.status === "queued" ? <Loader2 className="h-4 w-4 animate-spin text-cyan-200" /> : null}
              {activeJob.status === "failed" ? <XCircle className="h-4 w-4 text-red-300" /> : null}
              <StatusChip status={activeJob.status} />
            </div>
          </CardContent>
        </Card>
      )}

      {error && <ErrorState title="Upload failed" message={error} />}
    </div>
  );
}

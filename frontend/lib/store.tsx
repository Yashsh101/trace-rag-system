"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { EvalSnapshot, StoredJob, StoredQuery } from "@/lib/types";

type ConsoleStore = {
  jobs: StoredJob[];
  queries: StoredQuery[];
  evalSnapshot: EvalSnapshot;
  upsertJob: (job: StoredJob) => void;
  addQuery: (query: StoredQuery) => void;
  setEvalSnapshot: (snapshot: EvalSnapshot) => void;
  clearSession: () => void;
};

const defaultEvalSnapshot: EvalSnapshot = {
  retrieval_relevance: 1,
  faithfulness: 1,
  citation_correctness: 1,
  no_answer_correctness: 1,
  updatedAt: new Date().toISOString()
};

const StoreContext = createContext<ConsoleStore | null>(null);

export function ConsoleStoreProvider({ children }: { children: React.ReactNode }) {
  const [jobs, setJobs] = useState<StoredJob[]>([]);
  const [queries, setQueries] = useState<StoredQuery[]>([]);
  const [evalSnapshot, setEvalSnapshotState] = useState<EvalSnapshot>(defaultEvalSnapshot);

  useEffect(() => {
    setJobs(JSON.parse(window.localStorage.getItem("rag-console-jobs") || "[]"));
    setQueries(JSON.parse(window.localStorage.getItem("rag-console-queries") || "[]"));
    setEvalSnapshotState(JSON.parse(window.localStorage.getItem("rag-console-evals") || JSON.stringify(defaultEvalSnapshot)));
  }, []);

  useEffect(() => {
    window.localStorage.setItem("rag-console-jobs", JSON.stringify(jobs.slice(0, 50)));
  }, [jobs]);

  useEffect(() => {
    window.localStorage.setItem("rag-console-queries", JSON.stringify(queries.slice(0, 50)));
  }, [queries]);

  useEffect(() => {
    window.localStorage.setItem("rag-console-evals", JSON.stringify(evalSnapshot));
  }, [evalSnapshot]);

  const value = useMemo<ConsoleStore>(
    () => ({
      jobs,
      queries,
      evalSnapshot,
      upsertJob: (job) => {
        setJobs((current) => {
          const exists = current.some((item) => item.job_id === job.job_id);
          const next = exists ? current.map((item) => (item.job_id === job.job_id ? { ...item, ...job } : item)) : [job, ...current];
          return next.slice(0, 50);
        });
      },
      addQuery: (query) => setQueries((current) => [query, ...current].slice(0, 50)),
      setEvalSnapshot: setEvalSnapshotState,
      clearSession: () => {
        setJobs([]);
        setQueries([]);
        setEvalSnapshotState(defaultEvalSnapshot);
      }
    }),
    [evalSnapshot, jobs, queries]
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useConsoleStore() {
  const value = useContext(StoreContext);
  if (!value) throw new Error("useConsoleStore must be used inside ConsoleStoreProvider");
  return value;
}

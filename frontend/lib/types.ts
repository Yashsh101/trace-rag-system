export type HealthResponse = {
  status: string;
  app: string;
};

export type ReadinessResponse = {
  status: "ready" | "not_ready";
  ready: boolean;
  checks: Record<string, { ok: boolean; error?: string; backend?: string; environment?: string; skipped?: boolean; reason?: string }>;
};

export type IngestResponse = {
  job_id: string;
  document_id: number;
  document_version_id: number | null;
  filename: string;
  chunk_count: number;
  status: IngestionStatus;
};

export type IngestionStatus = "queued" | "processing" | "completed" | "failed";

export type IngestionJob = {
  job_id: string;
  status: IngestionStatus;
  document_id: number | null;
  error_message: string | null;
  chunk_count: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
};

export type QueryRequest = {
  question: string;
  top_k?: number;
};

export type Citation = {
  label: string;
  chunk_id: number;
  document_id: number;
  filename: string;
  page_start: number | null;
  page_end: number | null;
  score: number;
  snippet: string;
};

export type QueryResponse = {
  trace_id: string;
  query_log_id: number | null;
  answer: string;
  citations: Citation[];
  no_answer: boolean;
};

export type RetrievedChunk = {
  chunk_id: number;
  document_id: number;
  filename: string;
  page_start: number | null;
  page_end: number | null;
  score: number;
  source: string;
  snippet: string;
};

export type QueryTrace = {
  query_log_id: number;
  trace_id: string;
  original_query: string;
  rewritten_query: string | null;
  retrieved_chunks: RetrievedChunk[];
  reranked_chunks: RetrievedChunk[];
  final_citations: Citation[];
  validation_result: Record<string, unknown>;
  model_usage: {
    model: string;
    prompt_tokens: number | null;
    completion_tokens: number | null;
    total_tokens: number | null;
    estimated_cost: number | null;
  };
  metrics: {
    query_latency_ms?: number;
    retrieval_latency_ms?: number;
    embedding_latency_ms?: number;
    llm_latency_ms?: number;
    empty_retrieval?: boolean;
    no_answer?: boolean;
    citation_failure?: boolean;
    estimated_cost?: number;
  };
  answer: string;
  status: string;
  auth: {
    user_id: string | null;
    groups: string[];
    role: string | null;
  };
  denied_retrieval_count: number;
};

export type ApiErrorPayload = {
  error?: {
    code: string;
    message: string;
    trace_id?: string;
  };
  detail?: unknown;
};

export type StoredQuery = QueryResponse & {
  question: string;
  createdAt: string;
  trace?: QueryTrace;
};

export type StoredJob = IngestionJob & {
  filename: string;
};

export type EvalSnapshot = {
  retrieval_relevance: number;
  faithfulness: number;
  citation_correctness: number;
  no_answer_correctness: number;
  updatedAt: string;
};

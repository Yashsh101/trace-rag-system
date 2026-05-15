import type {
  ApiErrorPayload,
  HealthResponse,
  IngestResponse,
  IngestionJob,
  QueryRequest,
  QueryResponse,
  QueryTrace,
  ReadinessResponse
} from "@/lib/types";

export class RagApiError extends Error {
  status: number;
  payload: ApiErrorPayload | null;

  constructor(message: string, status: number, payload: ApiErrorPayload | null) {
    super(message);
    this.name = "RagApiError";
    this.status = status;
    this.payload = payload;
  }
}

export type RagClientConfig = {
  baseUrl: string;
  apiKey: string;
};

export class RagApiClient {
  private baseUrl: string;
  private apiKey: string;

  constructor(config: RagClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/$/, "");
    this.apiKey = config.apiKey;
  }

  health() {
    return this.request<HealthResponse>("/api/v1/health", { auth: false });
  }

  readiness() {
    return this.request<ReadinessResponse>("/api/v1/health/ready", { auth: false });
  }

  async ingest(file: File, onProgress?: (progress: number) => void) {
    onProgress?.(12);
    const form = new FormData();
    form.append("file", file);
    onProgress?.(35);
    const response = await this.request<IngestResponse>("/api/v1/documents/ingest", {
      method: "POST",
      body: form
    });
    onProgress?.(100);
    return response;
  }

  job(jobId: string) {
    return this.request<IngestionJob>(`/api/v1/ingestion-jobs/${jobId}`);
  }

  query(payload: QueryRequest) {
    return this.request<QueryResponse>("/api/v1/query", {
      method: "POST",
      body: JSON.stringify(payload),
      headers: {
        "Content-Type": "application/json"
      }
    });
  }

  trace(queryLogId: number) {
    return this.request<QueryTrace>(`/api/v1/query/${queryLogId}/trace`);
  }

  private async request<T>(path: string, init: RequestInit & { auth?: boolean } = {}) {
    if (!this.baseUrl) {
      throw new RagApiError("API base URL is not configured. Set it in Settings or NEXT_PUBLIC_RAG_API_BASE_URL.", 0, null);
    }
    if (init.auth !== false && !this.apiKey) {
      throw new RagApiError("API key is not configured. Set it in Settings.", 0, null);
    }

    const headers = new Headers(init.headers);
    if (init.auth !== false) headers.set("X-API-Key", this.apiKey);

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        headers,
        cache: "no-store"
      });
    } catch (error) {
      throw new RagApiError(error instanceof Error ? error.message : "Network request failed", 0, null);
    }

    const text = await response.text();
    const payload = text ? (JSON.parse(text) as T | ApiErrorPayload) : null;
    if (!response.ok) {
      const apiPayload = payload as ApiErrorPayload | null;
      const message = apiPayload?.error?.message || `Request failed with HTTP ${response.status}`;
      throw new RagApiError(message, response.status, apiPayload);
    }
    return payload as T;
  }
}

"use client";

import { FormEvent, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Bot, Loader2, Send, User } from "lucide-react";
import { RagApiError } from "@/lib/api";
import type { QueryTrace, StoredQuery } from "@/lib/types";
import { useConsoleSettings } from "@/lib/settings";
import { useConsoleStore } from "@/lib/store";
import { PageHeader } from "@/components/page-header";
import { CitationCard } from "@/components/citation-card";
import { TraceViewer } from "@/components/trace-viewer";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  query?: StoredQuery;
};

export default function ChatPage() {
  const { client } = useConsoleSettings();
  const { addQuery } = useConsoleStore();
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [trace, setTrace] = useState<QueryTrace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = useMemo(() => question.trim().length >= 3 && !loading, [loading, question]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    const trimmed = question.trim();
    setQuestion("");
    setError(null);
    setLoading(true);
    setMessages((current) => [...current, { role: "user", content: trimmed }]);
    try {
      const response = await client.query({ question: trimmed });
      const nextTrace = response.query_log_id ? await client.trace(response.query_log_id) : null;
      const stored: StoredQuery = { ...response, question: trimmed, createdAt: new Date().toISOString(), trace: nextTrace ?? undefined };
      addQuery(stored);
      setTrace(nextTrace);
      setMessages((current) => [...current, { role: "assistant", content: response.answer, query: stored }]);
    } catch (caught) {
      const message = caught instanceof RagApiError ? caught.message : caught instanceof Error ? caught.message : "Query failed.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <PageHeader title="RAG Chat" description="Ask source-grounded questions, inspect citations, and open the full retrieval trace." />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_440px]">
        <Card className="min-h-[calc(100vh-220px)]">
          <CardContent className="flex h-full min-h-[calc(100vh-220px)] flex-col p-0">
            <div className="flex-1 space-y-5 overflow-y-auto p-5">
              {messages.length === 0 && (
                <div className="flex h-full min-h-96 flex-col items-center justify-center text-center">
                  <Bot className="h-9 w-9 text-cyan-200" />
                  <div className="mt-4 text-lg font-semibold text-white">Ask against indexed documents</div>
                  <div className="mt-2 max-w-md text-sm leading-6 text-zinc-500">Answers are citation-gated. Unsupported questions should return a no-answer state instead of inventing facts.</div>
                </div>
              )}
              {messages.map((message, index) => (
                <motion.div key={`${message.role}-${index}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-white/10 bg-white/5">
                    {message.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4 text-cyan-200" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                      <p className="whitespace-pre-wrap text-sm leading-7 text-zinc-100">{message.content}</p>
                      {message.query && (
                        <div className="mt-4 flex flex-wrap gap-2">
                          <Badge>{message.query.no_answer ? "no answer" : "answered"}</Badge>
                          <Badge>trace {message.query.trace_id.slice(0, 10)}</Badge>
                          <Badge>query log {message.query.query_log_id ?? "n/a"}</Badge>
                        </div>
                      )}
                    </div>
                    {message.query?.citations.length ? (
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        {message.query.citations.map((citation) => (
                          <CitationCard key={`${message.query?.trace_id}-${citation.label}`} citation={citation} onClick={() => setTrace(message.query?.trace ?? null)} />
                        ))}
                      </div>
                    ) : null}
                  </div>
                </motion.div>
              ))}
              {loading && (
                <div className="flex gap-3">
                  <div className="h-8 w-8 rounded-md border border-white/10 bg-white/5" />
                  <div className="flex-1 space-y-3 rounded-lg border border-white/10 bg-white/[0.03] p-4">
                    <Skeleton className="h-4 w-2/3" />
                    <Skeleton className="h-4 w-5/6" />
                    <Skeleton className="h-4 w-1/2" />
                  </div>
                </div>
              )}
            </div>
            <div className="border-t border-white/10 p-4">
              {error && <div className="mb-3"><ErrorState title="Query failed" message={error} /></div>}
              <form onSubmit={submit} className="flex gap-3">
                <Textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a grounded question..." className="min-h-12 flex-1" />
                <Button type="submit" size="icon" disabled={!canSubmit} title="Send query">
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                </Button>
              </form>
            </div>
          </CardContent>
        </Card>
        <TraceViewer trace={trace} />
      </div>
    </div>
  );
}

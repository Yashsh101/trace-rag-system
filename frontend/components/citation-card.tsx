"use client";

import { FileText, Hash, Layers } from "lucide-react";
import { motion } from "framer-motion";
import type { Citation } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function CitationCard({ citation, onClick }: { citation: Citation; onClick?: () => void }) {
  return (
    <motion.button
      type="button"
      whileHover={{ y: -2 }}
      onClick={onClick}
      className="w-full text-left"
      title="Open citation in trace panel"
    >
      <Card className="border-cyan-300/15 bg-cyan-300/5 transition-colors hover:border-cyan-300/35">
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <FileText className="h-4 w-4 shrink-0 text-cyan-200" />
              <div className="truncate text-sm font-medium text-white">{citation.filename}</div>
            </div>
            <Badge className="border-cyan-300/20 bg-cyan-300/10 text-cyan-100">{citation.label}</Badge>
          </div>
          <p className="mt-3 line-clamp-3 text-sm leading-6 text-zinc-300">{citation.snippet}</p>
          <div className="mt-4 flex flex-wrap gap-2 text-xs text-zinc-500">
            <span className="inline-flex items-center gap-1">
              <Layers className="h-3.5 w-3.5" />
              page {citation.page_start ?? "n/a"}
            </span>
            <span className="inline-flex items-center gap-1">
              <Hash className="h-3.5 w-3.5" />
              chunk {citation.chunk_id}
            </span>
            <span>score {citation.score.toFixed(4)}</span>
          </div>
        </CardContent>
      </Card>
    </motion.button>
  );
}

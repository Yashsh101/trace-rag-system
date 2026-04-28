import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatMs(value?: number | null) {
  if (value === null || value === undefined) return "n/a";
  if (value < 1000) return `${Math.round(value)} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

export function formatCost(value?: number | null) {
  if (value === null || value === undefined) return "$0.0000";
  return `$${value.toFixed(4)}`;
}

export function shortId(value?: string | number | null, length = 8) {
  if (value === null || value === undefined) return "n/a";
  const text = String(value);
  return text.length <= length ? text : text.slice(0, length);
}

export function classForStatus(status?: string) {
  switch (status) {
    case "ready":
    case "completed":
    case "ok":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
    case "processing":
    case "queued":
    case "not_ready":
      return "border-amber-400/30 bg-amber-400/10 text-amber-200";
    case "failed":
    case "error":
      return "border-red-400/30 bg-red-400/10 text-red-200";
    default:
      return "border-white/10 bg-white/5 text-zinc-300";
  }
}

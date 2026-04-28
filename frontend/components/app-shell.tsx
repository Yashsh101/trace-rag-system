"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Database, FileUp, MessageSquare, Moon, Settings, ShieldCheck, Workflow } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { useConsoleSettings } from "@/lib/settings";

const nav = [
  { href: "/", label: "Dashboard", icon: Activity },
  { href: "/upload", label: "Upload", icon: FileUp },
  { href: "/chat", label: "RAG Chat", icon: MessageSquare },
  { href: "/trace", label: "Trace", icon: Workflow },
  { href: "/settings", label: "Settings", icon: Settings }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { settings } = useConsoleSettings();

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="fixed inset-0 -z-10 bg-[radial-gradient(circle_at_20%_0%,rgba(103,232,249,0.12),transparent_28%),radial-gradient(circle_at_80%_10%,rgba(34,197,94,0.08),transparent_24%)]" />
      <aside className="fixed left-0 top-0 hidden h-screen w-72 border-r border-white/10 bg-zinc-950/80 px-4 py-5 backdrop-blur-xl lg:block">
        <Link href="/" className="flex items-center gap-3 px-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-cyan-300/20 bg-cyan-300/10">
            <Database className="h-5 w-5 text-cyan-200" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-wide text-white">Mini RAG Console</div>
            <div className="text-xs text-zinc-500">Retrieval operations</div>
          </div>
        </Link>

        <nav className="mt-8 space-y-1">
          {nav.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "relative flex h-10 items-center gap-3 rounded-md px-3 text-sm text-zinc-400 transition-colors hover:bg-white/6 hover:text-white",
                  active && "bg-white/8 text-white"
                )}
              >
                {active && <motion.div layoutId="active-nav" className="absolute inset-y-1 left-0 w-1 rounded-full bg-cyan-300" />}
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="absolute bottom-5 left-4 right-4 rounded-lg border border-white/10 bg-white/5 p-4">
          <div className="flex items-center justify-between">
            <Badge className="capitalize">{settings.mode}</Badge>
            <Moon className="h-4 w-4 text-zinc-500" />
          </div>
          <div className="mt-3 truncate text-xs text-zinc-500">{settings.apiBaseUrl}</div>
        </div>
      </aside>

      <main className="lg:pl-72">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-white/10 bg-zinc-950/70 px-4 backdrop-blur-xl lg:px-8">
          <div className="flex items-center gap-2 lg:hidden">
            <ShieldCheck className="h-5 w-5 text-cyan-200" />
            <span className="text-sm font-semibold">Mini RAG</span>
          </div>
          <div className="hidden text-sm text-zinc-500 lg:block">Production-grade local RAG observability and operations</div>
          <div className="flex items-center gap-2">
            <Badge className="border-cyan-300/20 bg-cyan-300/10 text-cyan-100">API connected by key</Badge>
          </div>
        </header>
        <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">{children}</div>
      </main>
    </div>
  );
}

"use client";

import { Moon, RotateCcw, Save, Server } from "lucide-react";
import { useTheme } from "next-themes";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { useConsoleSettings } from "@/lib/settings";
import { useConsoleStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";

export default function SettingsPage() {
  const { settings, updateSettings } = useConsoleSettings();
  const { clearSession } = useConsoleStore();
  const { theme, setTheme } = useTheme();
  const [apiBaseUrl, setApiBaseUrl] = useState(settings.apiBaseUrl);
  const [apiKey, setApiKey] = useState(settings.apiKey);
  const [prodMode, setProdMode] = useState(settings.mode === "prod");

  const save = () => {
    updateSettings({ apiBaseUrl, apiKey, mode: prodMode ? "prod" : "local" });
  };

  return (
    <div>
      <PageHeader title="Settings" description="Configure runtime connection details, API key auth, environment mode, and presentation." />
      <div className="grid gap-6 xl:grid-cols-[1fr_420px]">
        <Card>
          <CardHeader>
            <CardTitle>Backend Connection</CardTitle>
            <CardDescription>Requests are sent directly from the browser to FastAPI with the configured API key.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="api-url">API base URL</Label>
              <Input id="api-url" value={apiBaseUrl} onChange={(event) => setApiBaseUrl(event.target.value)} placeholder="https://your-api.railway.app" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="api-key">API key</Label>
              <Input id="api-key" value={apiKey} onChange={(event) => setApiKey(event.target.value)} type="password" />
            </div>
            <Separator />
            <div className="flex items-center justify-between rounded-md border border-white/10 bg-white/[0.03] p-4">
              <div>
                <div className="text-sm font-medium text-white">Production mode</div>
                <div className="mt-1 text-sm text-zinc-500">Tightens user expectations around real keys and production services.</div>
              </div>
              <Switch checked={prodMode} onCheckedChange={setProdMode} />
            </div>
            <Button onClick={save}>
              <Save className="h-4 w-4" />
              Save settings
            </Button>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Appearance</CardTitle>
              <CardDescription>Dark mode is optimized for operations consoles.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between rounded-md border border-white/10 bg-white/[0.03] p-4">
                <div className="flex items-center gap-3">
                  <Moon className="h-4 w-4 text-cyan-200" />
                  <div>
                    <div className="text-sm font-medium text-white">Dark theme</div>
                    <div className="text-xs text-zinc-500">Current: {theme}</div>
                  </div>
                </div>
                <Switch checked={theme !== "light"} onCheckedChange={(checked) => setTheme(checked ? "dark" : "light")} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Session Data</CardTitle>
              <CardDescription>Clear locally cached jobs, queries, and eval cards.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button variant="outline" onClick={clearSession}>
                <RotateCcw className="h-4 w-4" />
                Clear browser session
              </Button>
              <div className="flex items-start gap-3 rounded-md border border-white/10 bg-white/[0.03] p-4 text-sm text-zinc-500">
                <Server className="mt-0.5 h-4 w-4 text-zinc-400" />
                This does not delete backend documents, query logs, or ingestion jobs.
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

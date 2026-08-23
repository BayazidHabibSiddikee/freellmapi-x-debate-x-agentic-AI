"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Settings2, Loader2, Save } from "lucide-react";

export type Settings = {
  model: string;
  temperature: number;
  max_tokens: number;
  history_turns: number;
  rag_k: number;
  use_rag: boolean;
  dispatch_agent_default: "claude" | "opencode";
  dispatch_timeout_seconds: number;
  allow_file_writes: boolean;
};

const NUMERIC: Array<{ key: keyof Settings; label: string; step: string }> = [
  { key: "temperature", label: "Temperature", step: "0.1" },
  { key: "max_tokens", label: "Max tokens", step: "50" },
  { key: "history_turns", label: "History turns", step: "1" },
  { key: "rag_k", label: "RAG chunks (k)", step: "1" },
  { key: "dispatch_timeout_seconds", label: "Dispatch timeout (s)", step: "30" },
];

export function SettingsCard({
  tokenQS,
  settings,
  onSaved,
}: {
  tokenQS: () => string;
  settings: Settings | null;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<Settings | null>(settings);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  if (!settings) return null;
  const value = draft ?? settings;

  async function save() {
    if (!value) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch(`/api/business/settings?t=${tokenQS()}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(value),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
      setDraft(data);
      setMsg("Saved");
      onSaved();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Settings2 className="h-4 w-4" /> Settings
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-muted-foreground">
            Model
            <Input
              className="mt-1 h-8 text-sm"
              value={value.model}
              onChange={(e) => setDraft({ ...value, model: e.target.value })}
              placeholder="auto"
            />
          </label>
          <label className="text-xs text-muted-foreground">
            Default dispatch agent
            <select
              aria-label="Default dispatch agent"
              className="mt-1 w-full rounded border bg-transparent px-2 py-1.5 text-sm"
              value={value.dispatch_agent_default}
              onChange={(e) =>
                setDraft({
                  ...value,
                  dispatch_agent_default: e.target.value as "claude" | "opencode",
                })
              }
            >
              <option value="claude">claude</option>
              <option value="opencode">opencode</option>
            </select>
          </label>
          {NUMERIC.map(({ key, label, step }) => (
            <label key={key} className="text-xs text-muted-foreground">
              {label}
              <Input
                type="number"
                step={step}
                className="mt-1 h-8 text-sm"
                value={String(value[key])}
                onChange={(e) => setDraft({ ...value, [key]: Number(e.target.value) })}
              />
            </label>
          ))}
          <div className="flex flex-col justify-center gap-2 text-xs">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={Boolean(value.use_rag)}
                onChange={(e) => setDraft({ ...value, use_rag: e.target.checked })}
              />
              Inject RAG context into debates
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={Boolean(value.allow_file_writes)}
                onChange={(e) => setDraft({ ...value, allow_file_writes: e.target.checked })}
              />
              Allow dispatched agents to edit files
            </label>
          </div>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <Button size="sm" disabled={busy} onClick={save}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save settings
          </Button>
          {msg && <span className="text-xs text-muted-foreground">{msg}</span>}
        </div>
      </CardContent>
    </Card>
  );
}

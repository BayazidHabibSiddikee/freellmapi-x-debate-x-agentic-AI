"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Settings2, Loader2, Save, Bot, Trash2, Plus, Eye, EyeOff } from "lucide-react";

export type TelegramBotEntry = {
  id: string;
  name: string;
  bot_token: string;
  owner_email: string;
  gmails: string[];
  allowed_chat_ids: number[];
  active: boolean;
};

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
  auto_review?: boolean;
  active_project?: string | null;
  dispatch_max_retries?: number;
  team_review?: boolean;
  dispatch_max_parallel?: number;
  telegram_bots?: TelegramBotEntry[];
};

const NUMERIC: Array<{ key: keyof Settings; label: string; step: string }> = [
  { key: "temperature", label: "Temperature", step: "0.1" },
  { key: "max_tokens", label: "Max tokens", step: "50" },
  { key: "history_turns", label: "History turns", step: "1" },
  { key: "rag_k", label: "RAG chunks (k)", step: "1" },
  { key: "dispatch_timeout_seconds", label: "Dispatch timeout (s)", step: "30" },
  { key: "dispatch_max_retries", label: "Review retries (auto-loop)", step: "1" },
  { key: "dispatch_max_parallel", label: "Parallel agents", step: "1" },
];

function emptyBot(): TelegramBotEntry {
  return {
    id: `bot_${Date.now().toString(36)}`,
    name: "",
    bot_token: "",
    owner_email: "",
    gmails: [],
    allowed_chat_ids: [],
    active: true,
  };
}

function BotRow({
  bot,
  idx,
  total,
  showToken,
  onToggleToken,
  onChange,
  onRemove,
}: {
  bot: TelegramBotEntry;
  idx: number;
  total: number;
  showToken: boolean;
  onToggleToken: () => void;
  onChange: (patch: Partial<TelegramBotEntry>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="rounded-lg border bg-background p-3 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">
          Bot #{idx + 1} · <code>{bot.id}</code>
          {bot.active ? (
            <Badge variant="outline" className="ml-2 text-green-600">active</Badge>
          ) : (
            <Badge variant="outline" className="ml-2 text-muted-foreground">disabled</Badge>
          )}
        </span>
        <div className="flex items-center gap-1">
          <label className="flex items-center gap-1 text-xs cursor-pointer select-none">
            <input
              type="checkbox"
              checked={bot.active}
              onChange={(e) => onChange({ active: e.target.checked })}
            />
            Run
          </label>
          {total > 1 && (
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onRemove}>
              <Trash2 className="h-3 w-3 text-destructive" />
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <label className="text-xs text-muted-foreground">
          Display name
          <Input
            className="mt-1 h-8 text-sm"
            value={bot.name}
            onChange={(e) => onChange({ name: e.target.value })}
            placeholder="e.g. Alpha team bot"
          />
        </label>
        <label className="text-xs text-muted-foreground">
          Owner email
          <Input
            className="mt-1 h-8 text-sm"
            type="email"
            value={bot.owner_email}
            onChange={(e) => onChange({ owner_email: e.target.value })}
            placeholder="owner@example.com"
          />
        </label>
      </div>

      <label className="text-xs text-muted-foreground block">
        Bot token (from BotFather)
        <div className="mt-1 flex gap-2">
          <Input
            className="h-8 text-sm font-mono"
            type={showToken ? "text" : "password"}
            value={bot.bot_token}
            onChange={(e) => onChange({ bot_token: e.target.value })}
            placeholder="123456:ABC-DEF…"
          />
          <Button variant="outline" size="icon" className="h-8 w-8 shrink-0" onClick={onToggleToken}>
            {showToken ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </label>

      <label className="text-xs text-muted-foreground block">
        CC Gmail addresses (comma-separated)
        <Input
          className="mt-1 h-8 text-sm"
          value={bot.gmails.filter(Boolean).join(", ")}
          onChange={(e) =>
            onChange({ gmails: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })
          }
          placeholder="a@gmail.com, b@gmail.com"
        />
      </label>

      <label className="text-xs text-muted-foreground block">
        Allowed chat IDs (comma-separated; empty = any)
        <Input
          className="mt-1 h-8 text-sm"
          value={bot.allowed_chat_ids.filter(Boolean).join(", ")}
          onChange={(e) =>
            onChange({
              allowed_chat_ids: e.target.value
                .split(",")
                .map((s) => parseInt(s.trim(), 10))
                .filter((n) => !Number.isNaN(n)),
            })
          }
          placeholder="123456789, 987654321"
        />
      </label>
    </div>
  );
}

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
  const [showTokens, setShowTokens] = useState<Record<number, boolean>>({});

  if (!settings) return null;
  const value = draft ?? settings;
  const bots: TelegramBotEntry[] = value.telegram_bots ?? [];

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

  function updateBot(idx: number, patch: Partial<TelegramBotEntry>) {
    const next = [...bots];
    next[idx] = { ...next[idx], ...patch };
    setDraft({ ...value, telegram_bots: next });
  }

  function removeBot(idx: number) {
    const next = bots.filter((_, i) => i !== idx);
    setDraft({ ...value, telegram_bots: next });
  }

  return (
    <>
      {/* ── Telegram Bots card ── */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Bot className="h-4 w-4" />
            Telegram Bots
            {bots.length > 0 && (
              <Badge variant="secondary" className="ml-auto text-xs">
                {bots.filter((b) => b.active !== false).length} active
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {bots.length === 0 && (
            <p className="text-xs text-muted-foreground">
              No bots configured. Add one below to run a per-user Telegram bridge.
            </p>
          )}
          {bots.map((bot, idx) => (
            <BotRow
              key={bot.id}
              bot={bot}
              idx={idx}
              total={bots.length}
              showToken={!!showTokens[idx]}
              onToggleToken={() =>
                setShowTokens((prev) => ({ ...prev, [idx]: !prev[idx] }))
              }
              onChange={(patch) => updateBot(idx, patch)}
              onRemove={() => removeBot(idx)}
            />
          ))}
          <Button
            variant="outline"
            size="sm"
            className="text-xs"
            onClick={() => updateBot(bots.length, emptyBot())}
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            Add bot
          </Button>
          <p className="text-[11px] text-muted-foreground">
            Each bot runs as an independent daemon thread with its own session store.
            Start with: <code>python services/telegram/bot.py --poll</code> (all active) or{" "}
            <code>python services/telegram/bot.py --bot-name Alpha --poll</code>.
            Legacy single-bot mode still works via <code>TELEGRAM_BOT_TOKEN</code> env when no config exists.
          </p>
        </CardContent>
      </Card>

      {/* ── Existing settings card ── */}
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
                  checked={Boolean(value.auto_review)}
                  onChange={(e) => setDraft({ ...value, auto_review: e.target.checked })}
                />
                Auto-review dispatched work (Reviewer + Security)
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={Boolean(value.allow_file_writes)}
                  onChange={(e) => setDraft({ ...value, allow_file_writes: e.target.checked })}
                />
                Allow dispatched agents to edit files
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={value.team_review !== false}
                  onChange={(e) => setDraft({ ...value, team_review: e.target.checked })}
                />
                Team review loop (approve/reject + auto-retry on diff)
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
    </>
  );
}

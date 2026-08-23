"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Briefcase, Loader2, Send, RefreshCw, Gavel, Rocket } from "lucide-react";
import { Avatar, tokenQS, type Character } from "./avatar";
import { RolesCard, type RoleConfig } from "./roles-card";
import { CharactersBrowser } from "./characters-browser";
import { LogsCard } from "./logs-card";
import { SettingsCard, type Settings } from "./settings-card";

type Turn = { speaker: string; role?: string; text: string; used_rag?: boolean };
type Roster = {
  characters: Character[];
  roles: Record<string, RoleConfig>;
  role_list: string[];
  settings: Settings;
};

export default function BusinessPage() {
  const [roster, setRoster] = useState<Roster | null>(null);
  const [topic, setTopic] = useState("");
  const [history, setHistory] = useState<Turn[]>([]);
  const [busyRole, setBusyRole] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toolName, setToolName] = useState("");
  const [toolsForRole, setToolsForRole] = useState<Record<string, unknown>>({});
  const [toolBusy, setToolBusy] = useState(false);
  const [toolResult, setToolResult] = useState<string | null>(null);
  const [toolError, setToolError] = useState<string | null>(null);
  const [spec, setSpec] = useState<{
    goal?: string;
    subtasks?: Array<Record<string, unknown>>;
  } | null>(null);
  const [judgeBusy, setJudgeBusy] = useState(false);
  const [dispatchResult, setDispatchResult] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    fetch(`/api/business/roster?t=${tokenQS()}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("failed to load"))))
      .then(setRoster)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, busyRole]);

  const roles = roster?.roles ?? {};
  const activeRoles =
    roster?.role_list.filter((r) => (roles[r]?.members?.length ?? 0) > 0) ?? [];
  const firstActiveRole = activeRoles[0];

  // Load tools for the first active role
  useEffect(() => {
    if (!firstActiveRole) return;
    fetch(`/api/business/tools?role=${encodeURIComponent(firstActiveRole)}&t=${tokenQS()}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setToolsForRole(d?.tools ?? {}))
      .catch(() => setToolsForRole({}));
  }, [firstActiveRole, roster]);

  async function runTool() {
    if (!toolName || !firstActiveRole) return;
    setToolBusy(true);
    setToolError(null);
    setToolResult(null);
    try {
      const res = await fetch(`/api/business/tool-run?t=${tokenQS()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool: toolName, args: {}, role: firstActiveRole }),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error ?? `HTTP ${res.status}`);
      setToolResult(JSON.stringify(data.result, null, 2).slice(0, 4000));
    } catch (e) {
      setToolError(e instanceof Error ? e.message : "tool failed");
    } finally {
      setToolBusy(false);
    }
  }

  async function speak(role?: string) {
    if (!topic.trim() || busyRole) return;
    setError(null);
    setBusyRole(role ?? "__auto__");
    try {
      const res = await fetch(`/api/business/chat?t=${tokenQS()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, history, role }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
      setHistory((h) => [...h, data as Turn]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "request failed");
    } finally {
      setBusyRole(null);
    }
  }

  async function judgeAndDispatch() {
    if (!topic.trim() || judgeBusy) return;
    setJudgeBusy(true);
    setError(null);
    setSpec(null);
    setDispatchResult(null);
    try {
      const res = await fetch(`/api/business/judge?t=${tokenQS()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, history }),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error ?? `HTTP ${res.status}`);
      setSpec(data.spec);
    } catch (e) {
      setError(e instanceof Error ? e.message : "judge failed");
    } finally {
      setJudgeBusy(false);
    }
  }

  async function runSubtasks() {
    if (!spec || judgeBusy) return;
    setJudgeBusy(true);
    try {
      const res = await fetch(`/api/business/dispatch?t=${tokenQS()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spec }),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error ?? `HTTP ${res.status}`);
      setDispatchResult(
        JSON.stringify(data.summary) +
          "\n\n" +
          (data.results ?? [])
            .map(
              (r: { id?: string; status?: string; output?: string }) =>
                `${r.id}: ${r.status}${r.output ? `\n${String(r.output).slice(0, 400)}` : ""}`,
            )
            .join("\n\n"),
      );
      setHistory((h) => [
        ...h,
        {
          speaker: "Dispatcher",
          text: `Subtasks executed. Summary: ${JSON.stringify(data.summary)}. Review outputs above.`,
        },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "dispatch failed");
    } finally {
      setJudgeBusy(false);
    }
  }

  if (!roster) {
    return (
      <div className="container mx-auto max-w-4xl px-4 py-10 text-sm text-muted-foreground">
        {error ?? "Loading team…"}
      </div>
    );
  }

  const charByName = Object.fromEntries(roster.characters.map((c) => [c.name, c]));

  return (
    <div className="container mx-auto max-w-5xl px-4 py-6">
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Briefcase className="h-6 w-6" /> Business
          </h1>
          <p className="text-sm text-muted-foreground">
            Build your AI company: assign multiple characters per role, pin workspaces,
            debate with hybrid-RAG grounding, then dispatch subtasks to coding agents.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} title="Reload roster">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </header>

      <RolesCard
        tokenQS={tokenQS}
        characters={roster.characters}
        roles={roster.roles}
        roleList={roster.role_list}
        onChanged={load}
      />

      <CharactersBrowser
        tokenQS={tokenQS}
        characters={roster.characters}
        roles={roster.roles}
        roleList={roster.role_list}
        onAssign={(role, characterId) => {
          fetch(`/api/business/assign?t=${tokenQS()}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ role, add: characterId }),
          }).then(load);
        }}
      />

      <SettingsCard tokenQS={tokenQS} settings={roster.settings} onSaved={load} />

      {/* Team tools */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-sm font-medium">Team tools</CardTitle>
        </CardHeader>
        <CardContent>
          {activeRoles.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Assign a role above to unlock its tools (Researcher can download books and
              study them; every role can query the knowledge base).
            </p>
          ) : (
            <div className="flex flex-col gap-2 sm:flex-row">
              <select
                aria-label="Tool"
                value={toolName}
                onChange={(e) => setToolName(e.target.value)}
                className="rounded border bg-transparent px-2 py-1.5 text-sm"
              >
                <option value="">— pick tool —</option>
                {Object.entries(toolsForRole).map(([name, spec]) => (
                  <option key={name} value={name}>
                    {name} — {(spec as { description?: string }).description?.slice(0, 60)}
                  </option>
                ))}
              </select>
              <Button size="sm" disabled={!toolName || toolBusy} onClick={runTool}>
                {toolBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Run"}
              </Button>
            </div>
          )}
          {toolResult && (
            <pre className="mt-3 max-h-56 overflow-auto rounded bg-muted p-2 text-xs">
              {toolResult}
            </pre>
          )}
          {toolError && <p className="mt-2 text-xs text-destructive">{toolError}</p>}
        </CardContent>
      </Card>

      {/* Working session */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-sm font-medium">Working session</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Topic or goal — e.g. design the billing service for v2"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
            />
            <Button onClick={() => speak()} disabled={!topic.trim() || Boolean(busyRole)}>
              {busyRole === "__auto__" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
              Speak
            </Button>
          </div>
          <p className="mt-1.5 flex flex-wrap items-center text-xs text-muted-foreground">
            Or ask a specific role:
            {activeRoles.map((r) => (
              <Button
                key={r}
                variant="ghost"
                size="sm"
                className="ml-1 h-7 px-2 text-xs"
                disabled={!topic.trim() || Boolean(busyRole)}
                onClick={() => speak(r)}
              >
                {busyRole === r ? <Loader2 className="h-3 w-3 animate-spin" /> : r}
              </Button>
            ))}
          </p>

          {error && (
            <p className="mt-3 rounded border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
              {error}
            </p>
          )}

          <div className="mt-4 space-y-3">
            {history.length === 0 && (
              <p className="py-8 text-center text-sm text-muted-foreground">
                Set the topic and press Speak. Assigned characters respond in role,
                citing your knowledge base when it helps.
              </p>
            )}
            {history.map((turn, i) => (
              <div key={i} className="flex gap-3">
                <Avatar name={turn.speaker} id={charByName[turn.speaker]?.id} />
                <div className="min-w-0 flex-1 rounded-lg border p-3">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="text-sm font-medium">{turn.speaker}</span>
                    {turn.role && (
                      <Badge variant="outline" className="text-[10px]">
                        {turn.role}
                      </Badge>
                    )}
                    {turn.used_rag && (
                      <Badge variant="secondary" className="text-[10px]">
                        RAG
                      </Badge>
                    )}
                  </div>
                  <p className="whitespace-pre-wrap text-sm">{turn.text}</p>
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Judge → coding agents */}
          <div className="mt-4 flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={!topic.trim() || history.length === 0 || judgeBusy}
              onClick={judgeAndDispatch}
              title="Distill the debate into a task spec"
            >
              {judgeBusy && !spec ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Gavel className="h-4 w-4" />
              )}
              Judge
            </Button>
            {spec && (
              <Button size="sm" disabled={judgeBusy} onClick={runSubtasks}>
                {judgeBusy ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Rocket className="h-4 w-4" />
                )}
                Dispatch {spec.subtasks?.length ?? 0} subtask(s)
              </Button>
            )}
          </div>
          {spec && (
            <pre className="mt-2 max-h-48 overflow-auto rounded bg-muted p-2 text-xs">
              {JSON.stringify(spec, null, 2).slice(0, 2500)}
            </pre>
          )}
          {dispatchResult && (
            <pre className="mt-2 max-h-56 overflow-auto rounded border p-2 text-xs">
              {dispatchResult.slice(0, 3000)}
            </pre>
          )}
        </CardContent>
      </Card>

      <LogsCard tokenQS={tokenQS} />
    </div>
  );
}

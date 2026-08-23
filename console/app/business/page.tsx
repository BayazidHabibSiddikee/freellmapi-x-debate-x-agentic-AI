"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Briefcase, Loader2, Send, RefreshCw } from "lucide-react";

type Character = {
  id: string;
  name: string;
  image?: string;
  system_prompt?: string;
};

type Roster = {
  characters: Character[];
  roles: Record<string, string | null>;
  role_list: string[];
};

type Turn = {
  speaker: string;
  role?: string;
  text: string;
  used_rag?: boolean;
};

function Avatar({ name, id }: { name: string; id?: string }) {
  const [failed, setFailed] = useState(false);
  if (failed || !id) {
    return (
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-muted font-mono text-xs">
        {name.slice(0, 2).toUpperCase()}
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`/api/business/avatar/${encodeURIComponent(id)}.card.png?t=${tokenQS()}`}
      alt={name}
      onError={() => setFailed(true)}
      className="h-10 w-10 shrink-0 rounded-full object-cover"
    />
  );
}

let _t: string | null = null;
function tokenQS() {
  if (_t === null) {
    const m = typeof window !== "undefined" ? window.location.search.match(/[?&]t=([a-f0-9]+)/) : null;
    _t = m ? m[1] : "";
    if (!_t && typeof document !== "undefined") {
      const c = document.cookie.match(/agentic_os_token=([a-f0-9]+)/);
      _t = c ? c[1] : "";
    }
  }
  return encodeURIComponent(_t);
}

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
  const bottomRef = useRef<HTMLDivElement>(null);

  const activeRoles0 = roster?.role_list.filter((r) => roster.roles[r]) ?? [];

  // Load tools for the first active role
  useEffect(() => {
    if (activeRoles0.length === 0) return;
    fetch(`/api/business/tools?role=${encodeURIComponent(activeRoles0[0])}&t=${tokenQS()}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setToolsForRole(d?.tools ?? {}))
      .catch(() => setToolsForRole({}));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roster]);

  async function runTool() {
    if (!toolName) return;
    setToolBusy(true);
    setToolError(null);
    setToolResult(null);
    try {
      const role = activeRoles0[0];
      const res = await fetch(`/api/business/tool-run?t=${tokenQS()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool: toolName, args: {}, role }),
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

  async function assign(role: string, characterId: string | null) {
    await fetch(`/api/business/assign?t=${tokenQS()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role, character_id: characterId }),
    });
    load();
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

  if (!roster) {
    return (
      <div className="container mx-auto max-w-4xl px-4 py-10 text-sm text-muted-foreground">
        {error ?? "Loading team…"}
      </div>
    );
  }

  const charById = Object.fromEntries(roster.characters.map((c) => [c.id, c]));
  const activeRoles = roster.role_list.filter((r) => roster.roles[r]);

  return (
    <div className="container mx-auto max-w-5xl px-4 py-6">
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Briefcase className="h-6 w-6" /> Business
          </h1>
          <p className="text-sm text-muted-foreground">
            Assign AI characters to company roles. Each role adds its mandate on top of the
            character&apos;s persona. Chat is grounded with hybrid RAG (BM25 + embeddings).
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} title="Reload roster">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </header>

      {/* Role assignment */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-sm font-medium">Roles</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          {roster.role_list.map((role) => {
            const assignedId = roster.roles[role];
            const assigned = assignedId ? charById[assignedId] : null;
            return (
              <div key={role} className="flex items-center gap-3 rounded-lg border p-3">
                {assigned ? (
                  <Avatar name={assigned.name} id={assigned.id} />
                ) : (
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-dashed font-mono text-[10px] text-muted-foreground">
                    ?
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
                      {role}
                    </span>
                    {assigned && <Badge variant="secondary" className="text-[10px]">assigned</Badge>}
                  </div>
                  <select
                    aria-label={`Assign ${role}`}
                    value={assignedId ?? ""}
                    onChange={(e) =>
                      assign(role, e.target.value === "" ? null : e.target.value)
                    }
                    className="mt-1 w-full rounded border bg-transparent px-1.5 py-1 text-sm"
                  >
                    <option value="">— unassigned —</option>
                    {roster.characters.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

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
              <Button
                size="sm"
                disabled={!toolName || toolBusy}
                onClick={runTool}
              >
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
      <Card>
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
          <p className="mt-1.5 text-xs text-muted-foreground">
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
                <Avatar
                  name={turn.speaker}
                  id={
                    roster.characters.find((c) => c.name === turn.speaker)?.id
                  }
                />
                <div className="min-w-0 flex-1 rounded-lg border p-3">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="text-sm font-medium">{turn.speaker}</span>
                    {turn.role && (
                      <Badge variant="outline" className="text-[10px]">{turn.role}</Badge>
                    )}
                    {turn.used_rag && (
                      <Badge variant="secondary" className="text-[10px]">RAG</Badge>
                    )}
                  </div>
                  <p className="whitespace-pre-wrap text-sm">{turn.text}</p>
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

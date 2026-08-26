"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Briefcase, Loader2, Send, RefreshCw, Gavel, Rocket, BookPlus, ListChecks } from "lucide-react";
import { Avatar, tokenQS, type Character } from "./avatar";
import { RolesCard, type RoleConfig } from "./roles-card";
import { CharactersBrowser } from "./characters-browser";
import { TeamsCard, type Team } from "./teams-card";
import { ProjectsCard, type Project } from "./projects-card";
import { LogsCard } from "./logs-card";
import { SettingsCard, type Settings } from "./settings-card";
import { DispatchQueueCard } from "./dispatch-queue-card";

type Turn = { speaker: string; role?: string; text: string; used_rag?: boolean };
type Roster = {
  characters: Character[];
  roles: Record<string, RoleConfig>;
  role_list: string[];
  settings: Settings;
  projects?: Project[];
  teams?: Team[];
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
  const [ingestMsg, setIngestMsg] = useState<string | null>(null);
  const [ingesting, setIngesting] = useState(false);
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
      const rev = data.review_summary;
      const reviewLine = rev && rev.total > 0
        ? `\n\n[Auto-review] ${rev.total} passed, ${rev.rejects} rejected${rev.needs_attention ? ' ⚠ attention needed' : ''}`
        : '';
      setDispatchResult(
        JSON.stringify(data.summary) + reviewLine +
          "\n\n" +
          (data.results ?? [])
            .map(
              (r: { id?: string; status?: string; output?: string; reviews?: Array<Record<string, unknown>> }) =>
                `${r.id}: ${r.status}${r.output ? `\n${String(r.output).slice(0, 400)}` : ""}` +
                (r.reviews?.length
                  ? `\nReviews:\n${r.reviews
                      .map((rv) => {
                        const v = rv as Record<string, unknown>;
                        const who = (v.reviewer as string) ?? v.kind;
                        const verdict = (v.verdict as string) ?? v.raw;
                        const fb = (v.feedback as string) ?? "";
                        return `  [${who ?? "?"}] ${verdict ?? ""}${fb ? ` — ${fb}` : ""}`;
                      })
                      .join("\n")}`
                  : ""),
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

  async function runQueueSubtasks() {
    if (!spec) return;
    setJudgeBusy(true);
    setError(null);
    try {
      const activeProject = roster?.projects?.find(
        (p) => p.id === roster?.settings?.active_project,
      );
      const res = await fetch(`/api/business/jobs?t=${tokenQS()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          spec,
          project: activeProject
            ? { id: activeProject.id, name: activeProject.name, folder: activeProject.folder }
            : {},
        }),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error ?? `HTTP ${res.status}`);
      setDispatchResult(
        `Queued job ${data.job?.id} — ${data.job?.subtasks ?? 0} subtask(s) running in parallel.\n` +
          `Track progress in the Dispatch Queue below.`,
      );
      setHistory((h) => [
        ...h,
        {
          speaker: "Dispatcher",
          text: `Queued ${data.job?.subtasks ?? 0} subtask(s) as job ${data.job?.id} (parallel, ${roster?.projects?.length ?? 0} project(s)).`,
        },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "enqueue failed");
    } finally {
      setJudgeBusy(false);
    }
  }

  async function ingestTranscript() {
    if (ingesting || history.length === 0) return;
    setIngesting(true);
    setIngestMsg(null);
    try {
      const res = await fetch(`/api/business/ingest-transcript?t=${tokenQS()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, history }),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error ?? `HTTP ${res.status}`);
      setIngestMsg(data.message ?? "Ingested");
    } catch (e) {
      setIngestMsg(e instanceof Error ? e.message : "ingest failed");
    } finally {
      setIngesting(false);
    }
  }

  if (!roster) {
    return (
      <div className="container mx-auto max-w-4xl px-6 py-10 text-sm text-[hsl(var(--fg-dim))]">
        {error ?? "Loading team…"}
      </div>
    );
  }

  const charByName = Object.fromEntries(roster.characters.map((c) => [c.name, c]));

  return (
    <div className="flex flex-col">
      {/* ── Hero strip ── */}
      <section className="hero-glow border-b border-[hsl(var(--border-default))] px-6 py-8">
        <div className="container mx-auto max-w-6xl">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-[hsl(var(--fg-primary))]">
                <Briefcase className="h-5 w-5 text-[hsl(var(--accent-base))]" />
                Business
              </h1>
              <p className="mt-2 max-w-xl text-sm text-[hsl(var(--fg-secondary))] leading-relaxed">
                Build your AI company: assign multiple characters per role, pin workspaces,
                debate with hybrid-RAG grounding, then dispatch subtasks to coding agents.
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <a
                href="/business/rooms"
                className="label-uppercase hidden sm:inline-flex items-center gap-1 text-[hsl(var(--fg-dim))] hover:text-[hsl(var(--fg-secondary))] transition-colors"
              >
                The Office (1-on-1 rooms) →
              </a>
              <Button variant="outline" size="sm" onClick={load} title="Reload roster">
                <RefreshCw className="h-3.5 w-3.5" />
                <span className="hidden sm:inline ml-1">Reload</span>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* ── Two-column body ── */}
      <section className="px-6 py-6">
        <div className="container mx-auto max-w-6xl">
          <div className="columns-1 lg:columns-[340px_1fr] gap-6">

            {/* ── Left column: config cards (scrolls) ── */}
            <div className="flex flex-col gap-4">

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

              <TeamsCard
                tokenQS={tokenQS}
                teams={roster.teams ?? []}
                onChanged={load}
              />

              <ProjectsCard
                tokenQS={tokenQS}
                characters={roster.characters}
                projects={roster.projects ?? []}
                activeId={roster.settings?.active_project ?? null}
                onChanged={load}
              />

              <DispatchQueueCard tokenQS={tokenQS} />

              <SettingsCard tokenQS={tokenQS} settings={roster.settings} onSaved={load} />

              {/* ── Team tools ── */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-sm font-medium">
                    <span className="label-uppercase">Team tools</span>
                    {firstActiveRole && (
                      <Badge variant="secondary" className="text-[10px]">
                        {firstActiveRole}
                      </Badge>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {activeRoles.length === 0 ? (
                    <p className="text-xs text-[hsl(var(--fg-dim))] leading-relaxed">
                      Assign a role above to unlock its tools (Researcher can download books and
                      study them; every role can query the knowledge base).
                    </p>
                  ) : (
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                      <div className="flex-1">
                        <label className="label-uppercase mb-1.5 block">Tool</label>
                        <select
                          aria-label="Select tool"
                          value={toolName}
                          onChange={(e) => setToolName(e.target.value)}
                          className="h-9 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          <option value="">— pick tool —</option>
                          {Object.entries(toolsForRole).map(([name, spec]) => (
                            <option key={name} value={name}>
                              {name} — {(spec as { description?: string }).description?.slice(0, 60)}
                            </option>
                          ))}
                        </select>
                      </div>
                      <Button size="sm" disabled={!toolName || toolBusy} onClick={runTool}>
                        {toolBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                        Run
                      </Button>
                    </div>
                  )}
                  {toolResult && (
                    <pre className="mt-3 overflow-x-auto rounded-md border border-[hsl(var(--border-subtle))] bg-[hsl(var(--bg-inset))] p-3 text-[11px] leading-relaxed text-[hsl(var(--fg-secondary))]">
                      {toolResult}
                    </pre>
                  )}
                  {toolError && (
                    <p className="mt-2 text-xs text-[hsl(var(--status-err))]">
                      {toolError}
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* ── Working session ── */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-sm font-medium">
                    <span className="label-uppercase">Working session</span>
                    {busyRole && (
                      <Badge variant="secondary" className="text-[10px] animate-pulse">
                        <Loader2 className="h-2.5 w-2.5 mr-1 animate-spin" />
                        {busyRole === "__auto__" ? "round-robin" : busyRole}
                      </Badge>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Topic input */}
                  <div className="flex gap-2">
                    <Input
                      placeholder="Topic or goal — e.g. design the billing service for v2"
                      value={topic}
                      onChange={(e) => setTopic(e.target.value)}
                      className="h-9 text-sm"
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          speak();
                        }
                      }}
                    />
                    <Button
                      onClick={() => speak()}
                      disabled={!topic.trim() || Boolean(busyRole)}
                      size="sm"
                    >
                      {busyRole === "__auto__" ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Send className="h-3.5 w-3.5" />
                      )}
                      Speak
                    </Button>
                  </div>

                  {/* Role buttons */}
                  {activeRoles.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[11px] text-[hsl(var(--fg-dim))]">Or ask:</span>
                      {activeRoles.map((r) => (
                        <Button
                          key={r}
                          variant={busyRole === r ? "default" : "ghost"}
                          size="sm"
                          className="h-7 px-2.5 text-xs"
                          disabled={!topic.trim() || Boolean(busyRole)}
                          onClick={() => speak(r)}
                        >
                          {busyRole === r ? (
                            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                          ) : null}
                          {r}
                        </Button>
                      ))}
                    </div>
                  )}

                  {/* Error display */}
                  {error && (
                    <div className="rounded-md border border-[hsl(var(--status-err-dim))] bg-[hsl(var(--status-err-dim))]/10 px-3 py-2 text-xs text-[hsl(var(--status-err))]">
                      {error}
                    </div>
                  )}

                  {/* Turn history */}
                  <div className="space-y-3">
                    {history.length === 0 && (
                      <div className="py-8 text-center">
                        <p className="text-sm text-[hsl(var(--fg-dim))] leading-relaxed">
                          Set the topic and press <strong className="text-[hsl(var(--fg-primary))]">Speak</strong>.
                          Assigned characters respond in role, citing your knowledge base when it helps.
                        </p>
                      </div>
                    )}
                    {history.map((turn, i) => (
                      <div key={i} className="flex gap-3">
                        <Avatar name={turn.speaker} id={charByName[turn.speaker]?.id} />
                        <div className="min-w-0 flex-1 rounded-lg border border-[hsl(var(--border-subtle))] bg-[hsl(var(--bg-surface))] px-3 py-2.5">
                          <div className="mb-1.5 flex items-center gap-2">
                            <span className="text-sm font-medium text-[hsl(var(--fg-primary))]">
                              {turn.speaker}
                            </span>
                            {turn.role && (
                              <Badge variant="outline" className="text-[9px] font-mono uppercase tracking-wide">
                                {turn.role}
                              </Badge>
                            )}
                            {turn.used_rag && (
                              <Badge variant="secondary" className="text-[9px]">
                                RAG
                              </Badge>
                            )}
                          </div>
                          <p className="whitespace-pre-wrap text-sm leading-relaxed text-[hsl(var(--fg-secondary))]">
                            {turn.text}
                          </p>
                        </div>
                      </div>
                    ))}
                    <div ref={bottomRef} />
                  </div>

                  {/* Judge + dispatch actions */}
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!topic.trim() || history.length === 0 || judgeBusy}
                      onClick={judgeAndDispatch}
                      title="Distill the debate into a task spec"
                    >
                      {judgeBusy && !spec ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Gavel className="h-3.5 w-3.5" />
                      )}
                      Judge
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={history.length === 0 || ingesting}
                      onClick={ingestTranscript}
                      title="Store this debate in the knowledge base so future debates can cite it"
                    >
                      {ingesting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BookPlus className="h-3.5 w-3.5" />}
                      Ingest into KB
                    </Button>
                    {spec && (
                      <Button size="sm" disabled={judgeBusy} onClick={runSubtasks}>
                        {judgeBusy ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Rocket className="h-3.5 w-3.5" />
                        )}
                        Dispatch {spec.subtasks?.length ?? 0}
                      </Button>
                    )}
                    {spec && (
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={judgeBusy}
                        onClick={runQueueSubtasks}
                        title="Queue subtasks on the parallel worker pool (multi-project)"
                      >
                        {judgeBusy ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <ListChecks className="h-3.5 w-3.5" />
                        )}
                        Queue
                      </Button>
                    )}
                  </div>

                  {/* Spec preview */}
                  {spec && (
                    <details className="group mt-1">
                      <summary className="cursor-pointer text-xs text-[hsl(var(--fg-dim))] hover:text-[hsl(var(--fg-secondary))] transition-colors">
                        View generated spec ({JSON.stringify(spec).length} chars)
                      </summary>
                      <pre className="mt-2 overflow-x-auto rounded-md border border-[hsl(var(--border-subtle))] bg-[hsl(var(--bg-inset))] p-3 text-[11px] leading-relaxed text-[hsl(var(--fg-secondary))]">
                        {JSON.stringify(spec, null, 2).slice(0, 2500)}
                      </pre>
                    </details>
                  )}

                  {/* Ingest status */}
                  {ingestMsg && (
                    <p className="text-xs text-[hsl(var(--fg-dim))]">
                      {ingestMsg}
                    </p>
                  )}

                  {/* Dispatch result */}
                  {dispatchResult && (
                    <details className="group">
                      <summary className="cursor-pointer text-xs text-[hsl(var(--fg-dim))] hover:text-[hsl(var(--fg-secondary))] transition-colors">
                        View dispatch output ({dispatchResult.length} chars)
                      </summary>
                      <pre className="mt-2 overflow-x-auto rounded-md border border-[hsl(var(--border-subtle))] bg-[hsl(var(--bg-inset))] p-3 text-[11px] leading-relaxed text-[hsl(var(--fg-secondary))]">
                        {dispatchResult.slice(0, 3000)}
                      </pre>
                    </details>
                  )}
                </CardContent>
              </Card>

              <LogsCard tokenQS={tokenQS} />

            </div>

            {/* ── Right column: context panel (pinned) ── */}
            <div className="lg:sticky lg:top-6 lg:self-start space-y-4">

              {/* Active role indicator */}
              {firstActiveRole && (
                <Card>
                  <CardContent className="pt-4 pb-3">
                    <p className="label-uppercase mb-2">Active role</p>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="font-mono text-xs">
                        {firstActiveRole}
                      </Badge>
                      {roster.roles[firstActiveRole]?.members.length > 0 && (
                        <span className="text-xs text-[hsl(var(--fg-dim))]">
                          {roster.roles[firstActiveRole].members.length} member{roster.roles[firstActiveRole].members.length > 1 ? "s" : ""}
                        </span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Quick dispatch for active project */}
              {roster.settings?.active_project && (
                <Card>
                  <CardContent className="pt-4 pb-3">
                    <p className="label-uppercase mb-2">Active project</p>
                    <p className="text-sm font-medium text-[hsl(var(--fg-primary))]">
                      {roster.projects?.find(p => p.id === roster.settings.active_project)?.name ?? "—"}
                    </p>
                    <p className="mt-1 text-xs text-[hsl(var(--fg-dim))] break-all font-mono">
                      {roster.projects?.find(p => p.id === roster.settings.active_project)?.folder ?? ""}
                    </p>
                  </CardContent>
                </Card>
              )}

              {/* Dispatch queue (compact) */}
              <DispatchQueueCard tokenQS={tokenQS} />

            </div>

          </div>
        </div>
      </section>
    </div>
  );
}

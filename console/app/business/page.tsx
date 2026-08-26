"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Briefcase, Loader2, Send, RefreshCw, Gavel, Rocket, BookPlus, ListChecks, MessageSquare } from "lucide-react";
import { Avatar, tokenQS, type Character } from "./avatar";
import { RolesCard, type RoleConfig } from "./roles-card";
import { TeamsCard, type Team } from "./teams-card";
import { ProjectsCard, type Project } from "./projects-card";
import { LogsCard } from "./logs-card";
import { SettingsCard, type Settings as SettingsType } from "./settings-card";
import { DispatchQueueCard } from "./dispatch-queue-card";

type Turn = { speaker: string; role?: string; text: string; used_rag?: boolean };
type Roster = {
  characters: Character[];
  roles: Record<string, RoleConfig>;
  role_list: string[];
  settings: SettingsType;
  projects?: Project[];
  teams?: Team[];
};

export default function BusinessPage() {
  const [roster, setRoster] = useState<Roster | null>(null);
  const [topic, setTopic] = useState("");
  const [history, setHistory] = useState<Turn[]>([]);
  const [busyRole, setBusyRole] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
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
    if (history.length === 0) return;
    try {
      const res = await fetch(`/api/business/ingest-transcript?t=${tokenQS()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, history }),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error ?? `HTTP ${res.status}`);
    } catch {
      // silent
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
    <div className="flex flex-col min-h-0">
      {/* ── Minimal header ── */}
      <section className="border-b border-[hsl(var(--border-default))] px-6 py-4">
        <div className="container mx-auto max-w-5xl flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Briefcase className="h-4 w-4 text-[hsl(var(--accent-base))]" />
            <h1 className="text-lg font-semibold text-[hsl(var(--fg-primary))]">Business</h1>
          </div>
          <Button variant="ghost" size="sm" onClick={load} title="Reload">
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>
      </section>

      {/* ── Main content ── */}
      <section className="flex-1 overflow-auto px-6 py-4">
        <div className="container mx-auto max-w-5xl">
          <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">

            {/* ── Sidebar: config ── */}
            <div className="flex flex-col gap-3">
              <RolesCard
                tokenQS={tokenQS}
                characters={roster.characters}
                roles={roster.roles}
                roleList={roster.role_list}
                onChanged={load}
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

              <SettingsCard tokenQS={tokenQS} settings={roster.settings} onSaved={load} />

              <DispatchQueueCard tokenQS={tokenQS} />
            </div>

            {/* ── Main: working session ── */}
            <div className="flex flex-col gap-3">

              {/* Topic input */}
              <Card>
                <CardContent className="pt-4 pb-3">
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
                    </Button>
                  </div>

                  {/* Role buttons */}
                  {activeRoles.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 mt-2">
                      <span className="text-[11px] text-[hsl(var(--fg-dim))]">Ask:</span>
                      {activeRoles.map((r) => (
                        <Button
                          key={r}
                          variant={busyRole === r ? "default" : "ghost"}
                          size="sm"
                          className="h-6 px-2 text-[11px]"
                          disabled={!topic.trim() || Boolean(busyRole)}
                          onClick={() => speak(r)}
                        >
                          {busyRole === r && <Loader2 className="h-2.5 w-2.5 mr-1 animate-spin" />}
                          {r}
                        </Button>
                      ))}
                    </div>
                  )}

                  {error && (
                    <p className="mt-2 text-xs text-[hsl(var(--status-err))]">{error}</p>
                  )}
                </CardContent>
              </Card>

              {/* Chat history */}
              <Card>
                <CardContent className="pt-4 pb-3">
                  {history.length === 0 ? (
                    <div className="py-6 text-center">
                      <MessageSquare className="h-8 w-8 mx-auto mb-2 text-[hsl(var(--fg-dim))]" />
                      <p className="text-sm text-[hsl(var(--fg-dim))]">
                        Set a topic and press <strong>Send</strong> or ask a specific role.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3 max-h-[50vh] overflow-auto">
                      {history.map((turn, i) => (
                        <div key={i} className="flex gap-3">
                          <Avatar name={turn.speaker} id={charByName[turn.speaker]?.id} />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-sm font-medium text-[hsl(var(--fg-primary))]">
                                {turn.speaker}
                              </span>
                              {turn.role && (
                                <Badge variant="outline" className="text-[9px] font-mono uppercase">
                                  {turn.role}
                                </Badge>
                              )}
                              {turn.used_rag && (
                                <Badge variant="secondary" className="text-[9px]">RAG</Badge>
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
                  )}
                </CardContent>
              </Card>

              {/* Action bar */}
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!topic.trim() || history.length === 0 || judgeBusy}
                  onClick={judgeAndDispatch}
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
                  disabled={history.length === 0}
                  onClick={ingestTranscript}
                >
                  <BookPlus className="h-3.5 w-3.5" />
                  Ingest
                </Button>
                {spec && (
                  <>
                    <Button size="sm" disabled={judgeBusy} onClick={runSubtasks}>
                      {judgeBusy ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Rocket className="h-3.5 w-3.5" />
                      )}
                      Dispatch {spec.subtasks?.length ?? 0}
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={judgeBusy}
                      onClick={runQueueSubtasks}
                    >
                      <ListChecks className="h-3.5 w-3.5" />
                      Queue
                    </Button>
                  </>
                )}
              </div>

              {/* Spec + dispatch output */}
              {spec && (
                <details className="group">
                  <summary className="cursor-pointer text-xs text-[hsl(var(--fg-dim))] hover:text-[hsl(var(--fg-secondary))]">
                    Spec ({JSON.stringify(spec).length} chars)
                  </summary>
                  <pre className="mt-2 overflow-x-auto rounded border border-[hsl(var(--border-subtle))] bg-[hsl(var(--bg-inset))] p-3 text-[11px] text-[hsl(var(--fg-secondary))]">
                    {JSON.stringify(spec, null, 2).slice(0, 2000)}
                  </pre>
                </details>
              )}
              {dispatchResult && (
                <details className="group">
                  <summary className="cursor-pointer text-xs text-[hsl(var(--fg-dim))] hover:text-[hsl(var(--fg-secondary))]">
                    Dispatch output ({dispatchResult.length} chars)
                  </summary>
                  <pre className="mt-2 overflow-x-auto rounded border border-[hsl(var(--border-subtle))] bg-[hsl(var(--bg-inset))] p-3 text-[11px] text-[hsl(var(--fg-secondary))]">
                    {dispatchResult.slice(0, 2000)}
                  </pre>
                </details>
              )}

              <LogsCard tokenQS={tokenQS} />
            </div>

          </div>
        </div>
      </section>
    </div>
  );
}

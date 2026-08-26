"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ListChecks, RefreshCw, Loader2, Ban, ChevronDown, ChevronRight } from "lucide-react";

type JobRow = {
  id: string;
  project_id?: string | null;
  project_name?: string | null;
  goal?: string;
  status: "pending" | "running" | "done" | "failed" | "cancelled";
  created_at?: string;
  subtasks: number;
  done: number;
};

type RunRow = {
  id: number;
  task_id: string;
  title: string;
  cwd: string;
  agent: string;
  status: string;
  output?: string;
  diff?: { is_git?: boolean; files?: string[]; stat?: string };
  review?: { approved?: boolean; approve?: number; reject?: number };
  error?: string;
  attempts?: number;
};

const STATUS_STYLE: Record<string, string> = {
  running: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  pending: "bg-muted text-muted-foreground border-border",
  done: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  failed: "bg-red-500/15 text-red-400 border-red-500/30",
  cancelled: "bg-amber-500/15 text-amber-500 border-amber-500/30",
};

export function DispatchQueueCard({ tokenQS }: { tokenQS: () => string }) {
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<{ runs: RunRow[]; done: number; total: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [detailBusy, setDetailBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const anyActive = jobs.some((j) => j.status === "running" || j.status === "pending");
const load = useCallback(
    async (silent = false) => {
      if (!silent) setBusy(true);
      try {
        const res = await fetch(`/api/business/jobs?t=${tokenQS()}`);
        const data = await res.json();
        if (data.ok !== false) setJobs(data.jobs ?? []);
      } catch {
        /* keep last known list */
      } finally {
        setBusy(false);
      }
    },
    [tokenQS],
  );

  useEffect(() => {
    load();
  }, [load]);

  // Poll while something is running.
  useEffect(() => {
    if (timer.current) clearInterval(timer.current);
    if (anyActive) {
      timer.current = setInterval(() => load(true), 4000);
    }
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [anyActive, load]);

  async function toggle(id: string) {
    if (expanded === id) {
      setExpanded(null);
      setDetail(null);
      return;
    }
    setExpanded(id);
    setDetailBusy(true);
    try {
      const res = await fetch(`/api/business/jobs/${id}?t=${tokenQS()}`);
      const data = await res.json();
      const j = data.job;
      setDetail({ runs: j?.runs ?? [], done: j?.done ?? 0, total: j?.total ?? 0 });
    } catch {
      setDetail(null);
    } finally {
      setDetailBusy(false);
    }
  }

  async function cancelJob(id: string) {
    setMsg(null);
    const res = await fetch(`/api/business/jobs/${id}?t=${tokenQS()}`, { method: "POST" });
    const data = await res.json();
    setMsg(data.ok ? "Job cancelled" : data.error ?? "cancel failed");
    load();
  }

  return (
    <Card className="mb-6">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <ListChecks className="h-4 w-4" /> Dispatch Queue (parallel, multi-project)
        </CardTitle>
        <Button variant="outline" size="sm" className="h-7" onClick={() => load()}>
          {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
          Refresh
        </Button>
      </CardHeader>
      <CardContent>
        {msg && <p className="mb-2 text-xs text-muted-foreground">{msg}</p>}
        {jobs.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No dispatch jobs yet — hit &ldquo;Dispatch (queue)&rdquo; after judging to run subtasks in
            parallel across your projects.
          </p>
        ) : (
          <ul className="space-y-2">
            {jobs.map((j) => (
              <li key={j.id} className="rounded-lg border p-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-1 text-[10px]"
                    onClick={() => toggle(j.id)}
                  >
                    {expanded === j.id ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                  </Button>
                  <Badge className={STATUS_STYLE[j.status] ?? "bg-muted text-muted-foreground border-border"}>
                    {j.status}
                  </Badge>
                  <span className="font-mono text-[11px] text-muted-foreground">{j.id}</span>
                  <span className="min-w-0 flex-1 truncate text-xs">
                    {j.project_name ? `${j.project_name} · ` : ""}
                    {j.goal ?? "…"}
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    {j.done}/{j.subtasks} done
                  </span>
                  {(j.status === "running" || j.status === "pending") && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-1 text-[10px]"
                      onClick={() => cancelJob(j.id)}
                      title="Cancel job"
                    >
                      <Ban className="h-3 w-3" />
                    </Button>
                  )}
                </div>
                {j.subtasks > 0 && (
                  <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full bg-primary transition-all"
                      style={{ width: `${Math.round((j.done / j.subtasks) * 100)}%` }}
                    />
                  </div>
                )}
                {expanded === j.id && (
                  <div className="mt-2 space-y-1 border-t pt-2">
                    {detailBusy ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      (detail?.runs ?? []).map((r) => {
                        const files = (r.diff as { files?: string[] } | undefined)?.files?.length ?? 0;
                        return (
                          <div key={r.id} className="flex items-center gap-2 text-[11px]">
                            <Badge className={STATUS_STYLE[r.status] ?? "bg-muted"}>
                              {r.status}
                            </Badge>
                            <span className="truncate">{r.title || r.task_id}</span>
                            <span className="truncate text-muted-foreground">{r.cwd}</span>
                            {r.attempts && r.attempts > 1 && (
                              <span className="text-amber-500">×{r.attempts}</span>
                            )}
                            {files > 0 && (
                              <span className="text-emerald-500">{files} file(s)</span>
                            )}
                            {r.review && (
                              <span className={r.review.approved ? "text-emerald-500" : "text-red-400"}>
                                {r.review.approved ? "approved" : "rejected"}
                              </span>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
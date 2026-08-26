"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Play, RotateCcw, CheckCircle2, Clock } from "lucide-react";
import { tokenQS } from "@/app/business/avatar";

type Iteration = {
  iteration: number;
  title: string;
  hook: string;
  hashtags: string[];
  video: string;
  timestamp: string;
  status: string;
};

type PipelineStatus = {
  script_exists: boolean;
  iterations_done: number;
  summary: Iteration[];
};

export function PipelineRunnerCard() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [running, setRunning] = useState(false);
  const [pid, setPid] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  const refresh = useCallback(() => {
    fetch(`/api/business/pipeline?t=${tokenQS()}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("load failed"))))
      .then(setStatus)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(refresh, [refresh]);

  // Poll status while pipeline is running
  useEffect(() => {
    if (!polling) return;
    const iv = setInterval(() => {
      fetch(`/api/business/pipeline?t=${tokenQS()}`)
        .then((r) => r.json())
        .then((data: PipelineStatus) => {
          setStatus(data);
          if (data.iterations_done >= 10) {
            setPolling(false);
            setRunning(false);
          }
        })
        .catch(() => {});
    }, 3000);
    return () => clearInterval(iv);
  }, [polling]);

  async function runPipeline() {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch(`/api/business/pipeline?t=${tokenQS()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "run" }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error ?? "launch failed");
      setPid(data.pid);
      setPolling(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
      setRunning(false);
    }
  }

  async function resetPipeline() {
    setRunning(true);
    try {
      await fetch(`/api/business/pipeline?t=${tokenQS()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "reset" }),
      });
      refresh();
    } finally {
      setRunning(false);
    }
  }

  const done = status?.iterations_done ?? 0;
  const pct = Math.round((done / 10) * 100);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          Content Pipeline — Izuku Midoriya
          {running && <Loader2 className="h-4 w-4 animate-spin" />}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Runs 10 iterations: story → images → voice → video → post to social media.
        </p>

        {/* Progress bar */}
        <div className="relative h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full bg-primary transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{done}/10 iterations complete</span>
          <span>{pct}%</span>
        </div>

        {/* Controls */}
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={runPipeline}
            disabled={running || done >= 10}
          >
            {running ? (
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            ) : (
              <Play className="mr-1 h-3 w-3" />
            )}
            {done >= 10 ? "Complete" : running ? "Running..." : "Run Pipeline"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={resetPipeline}
            disabled={running}
          >
            <RotateCcw className="mr-1 h-3 w-3" />
            Reset
          </Button>
          <Button size="sm" variant="ghost" onClick={refresh}>
            Refresh
          </Button>
        </div>

        {pid && (
          <p className="text-xs text-muted-foreground">PID: {pid}</p>
        )}
        {error && (
          <p className="text-xs text-destructive">{error}</p>
        )}

        {/* Recent iterations */}
        {status?.summary && status.summary.length > 0 && (
          <div className="mt-2 space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Recent:</p>
            {status.summary.slice(-3).reverse().map((it) => (
              <div
                key={it.iteration}
                className="flex items-center gap-2 rounded border p-2 text-xs"
              >
                {it.status === "complete" ? (
                  <CheckCircle2 className="h-3 w-3 text-green-500" />
                ) : (
                  <Clock className="h-3 w-3 text-yellow-500" />
                )}
                <span className="font-medium">Ch {it.iteration}</span>
                <span className="truncate text-muted-foreground">{it.title}</span>
                <Badge variant="outline" className="ml-auto text-[10px]">
                  {it.status}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

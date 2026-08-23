"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FileText, Loader2 } from "lucide-react";

const LOG_FILES = [
  "activity.jsonl",
  "agent.log",
  "rag.log",
  "debate.log",
  "freellmapi.log",
  "console.log",
] as const;

export function LogsCard({ tokenQS }: { tokenQS: () => string }) {
  const [file, setFile] = useState<string>("activity.jsonl");
  const [lines, setLines] = useState<Array<{ n: number; text: string }>>([]);
  const [exists, setExists] = useState(true);
  const [busy, setBusy] = useState(false);
  const boxRef = useRef<HTMLPreElement>(null);

  const load = useCallback(() => {
    setBusy(true);
    fetch(`/api/business/logs?file=${encodeURIComponent(file)}&lines=300&t=${tokenQS()}`)
      .then((r) => r.json())
      .then((d) => {
        setLines(d.lines?.map((t: string, i: number) => ({ n: i + 1, text: t })) ?? []);
        setExists(Boolean(d.exists));
      })
      .catch(() => setLines([{ n: 1, text: "failed to load log" }]))
      .finally(() => setBusy(false));
  }, [file, tokenQS]);

  useEffect(load, [load]);
  useEffect(() => {
    boxRef.current?.scrollTo({ top: boxRef.current.scrollHeight });
  }, [lines]);

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <FileText className="h-4 w-4" /> Logs
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-2 flex flex-wrap items-center gap-1">
          {LOG_FILES.map((f) => (
            <Button
              key={f}
              variant={f === file ? "default" : "ghost"}
              size="sm"
              className="h-7 px-2 font-mono text-[11px]"
              onClick={() => setFile(f)}
            >
              {f}
            </Button>
          ))}
          <Button variant="outline" size="sm" className="ml-auto h-7" onClick={load}>
            {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : "Refresh"}
          </Button>
        </div>
        <pre
          ref={boxRef}
          className="max-h-72 overflow-auto rounded bg-muted p-2 text-[11px] leading-snug"
        >
          {exists
            ? lines.map((l) => `${String(l.n).padStart(4)} │ ${l.text}`).join("\n") || "— empty —"
            : `— ${file} does not exist yet (start the matching service) —`}
        </pre>
      </CardContent>
    </Card>
  );
}

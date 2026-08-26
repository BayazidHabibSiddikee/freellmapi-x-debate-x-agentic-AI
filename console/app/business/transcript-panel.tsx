"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FileText, ChevronDown, ChevronRight, ArrowRight } from "lucide-react";
import { tokenQS } from "./avatar";

type TranscriptEntry = {
  team: string;
  filename: string;
  path: string;
  size: number;
  modified: string;
  preview: string;
};

export function TranscriptPanel({
  onTransfer,
}: {
  onTransfer: (speaker: string, text: string) => void;
}) {
  const [transcripts, setTranscripts] = useState<TranscriptEntry[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [fullContent, setFullContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`/api/business/transcripts?action=list&t=${tokenQS()}`)
      .then(r => r.json())
      .then(d => setTranscripts(d.transcripts ?? []))
      .catch(() => {});
  }, []);

  async function loadFull(entry: TranscriptEntry) {
    if (expanded === entry.path) {
      setExpanded(null);
      setFullContent(null);
      return;
    }
    setExpanded(entry.path);
    setLoading(true);
    try {
      const res = await fetch(
        `/api/business/transcripts?action=read&path=${encodeURIComponent(entry.path)}&t=${tokenQS()}`
      );
      const d = await res.json();
      setFullContent(d.content ?? null);
    } catch {
      setFullContent(null);
    } finally {
      setLoading(false);
    }
  }

  function transferLastSpeaker() {
    if (!fullContent) return;
    // Extract last speaker block from the transcript
    const matches = [...fullContent.matchAll(/\*\*(.+?)\s*\((.+?)\)\*\*:\s*([\s\S]*?)(?=\n\*\*|\n---|\n\*Generated|$)/g)];
    if (matches.length === 0) return;
    const last = matches[matches.length - 1];
    const speaker = last[1].trim();
    const text = last[3].trim();
    onTransfer(speaker, text);
  }

  if (transcripts.length === 0) return null;

  const grouped = transcripts.reduce<Record<string, TranscriptEntry[]>>((acc, t) => {
    (acc[t.team] ??= []).push(t);
    return acc;
  }, {});

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-xs font-medium">
          <FileText className="h-3.5 w-3.5" />
          Transcripts
          <Badge variant="secondary" className="text-[9px] ml-auto">{transcripts.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-2 max-h-[30vh] overflow-auto">
          {Object.entries(grouped).map(([team, entries]) => (
            <div key={team}>
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-[10px] font-mono uppercase text-[hsl(var(--fg-dim))]">{team}</span>
                <span className="flex-1 border-t border-[hsl(var(--border-subtle))]" />
              </div>
              <div className="space-y-1">
                {entries.map(entry => (
                  <div key={entry.path}>
                    <button
                      className="flex items-center gap-1.5 w-full text-left px-2 py-1 rounded text-[11px] hover:bg-[hsl(var(--bg-inset))] transition-colors"
                      onClick={() => loadFull(entry)}
                    >
                      {expanded === entry.path ? (
                        <ChevronDown className="h-3 w-3 shrink-0 text-[hsl(var(--fg-dim))]" />
                      ) : (
                        <ChevronRight className="h-3 w-3 shrink-0 text-[hsl(var(--fg-dim))]" />
                      )}
                      <span className="truncate text-[hsl(var(--fg-secondary))]">
                        {entry.filename.replace("daily-", "").replace("debate-", "").replace(/\.md$/, "").replace("T", " ").replace(/-\d{3}Z$/, "")}
                      </span>
                      <span className="ml-auto text-[9px] text-[hsl(var(--fg-dim))]">
                        {Math.round(entry.size / 1024)}kb
                      </span>
                    </button>
                    {expanded === entry.path && (
                      <div className="ml-4 mt-1 p-2 rounded border border-[hsl(var(--border-subtle))] bg-[hsl(var(--bg-inset))]">
                        {loading ? (
                          <p className="text-[10px] text-[hsl(var(--fg-dim))]">Loading…</p>
                        ) : fullContent ? (
                          <>
                            <pre className="text-[10px] text-[hsl(var(--fg-secondary))] whitespace-pre-wrap max-h-[20vh] overflow-auto leading-relaxed">
                              {fullContent.slice(0, 3000)}
                            </pre>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 mt-2 text-[10px] gap-1"
                              onClick={transferLastSpeaker}
                            >
                              <ArrowRight className="h-3 w-3" />
                              Transfer to session
                            </Button>
                          </>
                        ) : (
                          <p className="text-[10px] text-[hsl(var(--fg-dim))]">No content</p>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

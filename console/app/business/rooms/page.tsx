"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { MessagesSquare, Send, Loader2 } from "lucide-react";
import { Avatar, tokenQS, type Character } from "../avatar";

type Msg = { role: string; speaker: string; content: string; ts: string };

export default function OfficePage() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selected, setSelected] = useState<Character | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`/api/business/roster?t=${tokenQS()}`)
      .then((r) => r.json())
      .then((d) => {
        const chars = d.characters as Character[];
        setCharacters(chars.sort((a, b) => a.name.localeCompare(b.name)));
      })
      .catch(() => {});
  }, []);

  const openRoom = useCallback(async (c: Character) => {
    setSelected(c);
    setMsgs([]);
    try {
      const res = await fetch(
        `/api/business/office?room=persona_${encodeURIComponent(c.id)}&t=${tokenQS()}`,
      );
      const data = await res.json();
      setMsgs(data.messages ?? []);
    } catch {
      /* new room */
    }
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  async function send() {
    if (!input.trim() || !selected || busy) return;
    const content = input.trim();
    setInput("");
    setBusy(true);
    setMsgs((m) => [
      ...m,
      { role: "user", speaker: "Sword", content, ts: new Date().toISOString() },
    ]);
    try {
      const res = await fetch(`/api/business/office?t=${tokenQS()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ character_id: selected.id, content }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setMsgs((m) => [
        ...m,
        {
          role: "persona",
          speaker: data.speaker ?? selected.name,
          content: data.text ?? "",
          ts: new Date().toISOString(),
        },
      ]);
    } catch (e) {
      setMsgs((m) => [
        ...m,
        { role: "system", speaker: "error", content: e instanceof Error ? e.message : "failed", ts: "" },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container mx-auto max-w-6xl px-4 py-6">
      <header className="mb-4">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <MessagesSquare className="h-6 w-6" /> The Office
        </h1>
        <p className="text-sm text-muted-foreground">
          Private 1-on-1 rooms with every person on the payroll. Everything said here
          is persisted in PostgreSQL — and each person remembers your past
          conversations next time you meet.{" "}
          <a href="/business" className="underline underline-offset-4 hover:text-foreground">
            ← Boardroom
          </a>
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-[280px_1fr]">
        {/* Persona list */}
        <Card className="self-start md:max-h-[70vh] md:overflow-y-auto">
          <CardContent className="p-2">
            {characters.map((c) => (
              <button
                key={c.id}
                onClick={() => openRoom(c)}
                className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm transition-colors ${
                  selected?.id === c.id ? "bg-accent/20 font-medium" : "hover:bg-muted"
                }`}
              >
                <Avatar name={c.name} id={c.id} className="h-7 w-7" textClass="text-[9px]" />
                <span className="truncate">{c.name}</span>
              </button>
            ))}
          </CardContent>
        </Card>

        {/* Chat pane */}
        <Card className="flex min-h-[60vh] flex-col">
          <CardHeader className="border-b py-3">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              {selected ? (
                <>
                  <Avatar name={selected.name} id={selected.id} className="h-8 w-8" />
                  {selected.name}
                  <Badge variant="outline" className="text-[10px]">
                    room persisted
                  </Badge>
                </>
              ) : (
                "Pick a person"
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col p-0">
            <div className="max-h-[52vh] min-h-[40vh] flex-1 space-y-3 overflow-y-auto p-4">
              {!selected && (
                <p className="pt-16 text-center text-sm text-muted-foreground">
                  Choose anyone from the roster — ask them about their job, debate a
                  decision privately, or just catch up. They remember.
                </p>
              )}
              {msgs.map((m, i) =>
                m.role === "user" ? (
                  <div key={i} className="ml-auto max-w-[80%] rounded-lg bg-accent/20 p-2.5 text-sm">
                    {m.content}
                  </div>
                ) : m.role === "system" ? (
                  <p key={i} className="text-center text-xs text-destructive">{m.content}</p>
                ) : (
                  <div key={i} className="mr-auto max-w-[80%] rounded-lg border p-2.5 text-sm">
                    <span className="mb-0.5 block text-[10px] uppercase tracking-wide text-muted-foreground">
                      {m.speaker}
                    </span>
                    {m.content}
                  </div>
                ),
              )}
              {busy && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" /> {selected?.name} is thinking…
                </div>
              )}
              <div ref={bottomRef} />
            </div>
            <div className="border-t p-3">
              <form
                className="flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  send();
                }}
              >
                <Input
                  placeholder={selected ? `Message ${selected.name}…` : "Select a person first"}
                  value={input}
                  disabled={!selected || busy}
                  onChange={(e) => setInput(e.target.value)}
                />
                <Button type="submit" size="icon" disabled={!selected || busy}>
                  <Send className="h-4 w-4" />
                </Button>
              </form>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

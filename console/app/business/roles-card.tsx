"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Users, X, MapPin } from "lucide-react";
import { Avatar, type Character } from "./avatar";

export type RoleConfig = { members: string[]; workspace?: string | null };

export function RolesCard({
  tokenQS,
  characters,
  roles,
  roleList,
  onChanged,
}: {
  tokenQS: () => string;
  characters: Character[];
  roles: Record<string, RoleConfig>;
  roleList: string[];
  onChanged: () => void;
}) {
  const [wsDraft, setWsDraft] = useState<Record<string, string>>({});
  const [wsMsg, setWsMsg] = useState<string | null>(null);

  const charById = Object.fromEntries(characters.map((c) => [c.id, c]));

  async function post(payload: Record<string, unknown>) {
    const res = await fetch(`/api/business/assign?t=${tokenQS()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.error ?? `HTTP ${res.status}`);
    }
    onChanged();
  }

  async function saveWorkspace(role: string) {
    setWsMsg(null);
    try {
      await post({ role, workspace: wsDraft[role] ?? roles[role]?.workspace ?? null });
      setWsMsg(`${role} workspace saved`);
    } catch (e) {
      setWsMsg(e instanceof Error ? e.message : "failed");
    }
  }

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Users className="h-4 w-4" /> Roles
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        {roleList.map((role) => {
          const cfg = roles[role] ?? { members: [], workspace: null };
          const unassigned = characters.filter((c) => !cfg.members.includes(c.id));
          return (
            <div key={role} className="rounded-lg border p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
                  {role}
                </span>
                {cfg.members.length > 0 && (
                  <Badge variant="secondary" className="text-[10px]">
                    {cfg.members.length} member{cfg.members.length > 1 ? "s" : ""}
                  </Badge>
                )}
              </div>

              {/* Member chips */}
              <div className="mb-2 flex flex-wrap gap-1.5">
                {cfg.members.length === 0 && (
                  <span className="text-xs text-muted-foreground">— empty —</span>
                )}
                {cfg.members.map((id) => {
                  const c = charById[id];
                  return (
                    <span
                      key={id}
                      className="inline-flex items-center gap-1.5 rounded-full border py-0.5 pl-0.5 pr-2 text-xs"
                      title={c?.system_prompt?.slice(0, 120)}
                    >
                      <Avatar name={c?.name ?? id} id={id} className="h-6 w-6" textClass="text-[9px]" />
                      <span className="max-w-24 truncate">{c?.name ?? id}</span>
                      <button
                        aria-label={`Remove ${c?.name ?? id} from ${role}`}
                        onClick={() => post({ role, remove: id }).catch(() => {})}
                        className="rounded-full p-0.5 hover:bg-muted"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  );
                })}
              </div>

              {/* Add member */}
              {unassigned.length > 0 && (
                <select
                  aria-label={`Add member to ${role}`}
                  value=""
                  onChange={(e) =>
                    e.target.value &&
                    post({ role, add: e.target.value }).catch(() => {})
                  }
                  className="mb-2 w-full rounded border bg-transparent px-1.5 py-1 text-xs"
                >
                  <option value="">+ add character…</option>
                  {unassigned.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              )}

              {/* Workspace */}
              <div className="flex items-center gap-1.5">
                <MapPin className="h-3 w-3 shrink-0 text-muted-foreground" />
                <Input
                  className="h-7 flex-1 font-mono text-[11px]"
                  placeholder="~/path/to/repo (workspace)"
                  value={wsDraft[role] ?? cfg.workspace ?? ""}
                  onChange={(e) => setWsDraft({ ...wsDraft, [role]: e.target.value })}
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 px-2 text-[11px]"
                  onClick={() => saveWorkspace(role)}
                >
                  Set
                </Button>
              </div>
            </div>
          );
        })}
        {wsMsg && <p className="text-xs text-muted-foreground sm:col-span-2">{wsMsg}</p>}
      </CardContent>
    </Card>
  );
}

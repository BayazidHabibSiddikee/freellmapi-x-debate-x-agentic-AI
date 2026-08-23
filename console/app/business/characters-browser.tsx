"use client";

import { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Users, Search } from "lucide-react";
import { Avatar, type Character } from "./avatar";
import type { RoleConfig } from "./roles-card";

export function CharactersBrowser({
  tokenQS,
  characters,
  roles,
  roleList,
  onAssign,
}: {
  tokenQS: () => string;
  characters: Character[];
  roles: Record<string, RoleConfig>;
  roleList: string[];
  onAssign: (role: string, characterId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);

  // Which roles each character currently holds
  const rolesOf = useMemo(() => {
    const map: Record<string, string[]> = {};
    for (const r of roleList) {
      for (const id of roles[r]?.members ?? []) {
        (map[id] ??= []).push(r);
      }
    }
    return map;
  }, [roles, roleList]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return characters;
    return characters.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        (c.system_prompt ?? "").toLowerCase().includes(q),
    );
  }, [characters, query]);

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Users className="h-4 w-4" /> Characters
          <Badge variant="secondary" className="text-[10px]">
            {characters.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative mb-3">
          <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="h-8 pl-7 text-sm"
            placeholder="Search by name or persona…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div className="grid max-h-96 grid-cols-2 gap-2 overflow-y-auto sm:grid-cols-3 lg:grid-cols-4">
          {filtered.map((c) => {
            const held = rolesOf[c.id] ?? [];
            const open = openId === c.id;
            return (
              <div
                key={c.id}
                className={`rounded-lg border p-2 transition-colors ${
                  open ? "border-[hsl(var(--accent-base))]" : "hover:bg-muted/50"
                }`}
              >
                <button
                  className="flex w-full items-center gap-2 text-left"
                  onClick={() => setOpenId(open ? null : c.id)}
                  title={c.system_prompt?.slice(0, 200)}
                >
                  <Avatar name={c.name} id={c.id} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-xs font-medium">{c.name}</span>
                    {held.length > 0 && (
                      <span className="block truncate font-mono text-[9px] uppercase text-muted-foreground">
                        {held.join(" · ")}
                      </span>
                    )}
                  </span>
                </button>

                {open && (
                  <div className="mt-2 border-t pt-2">
                    <p className="mb-2 line-clamp-3 text-[10px] leading-snug text-muted-foreground">
                      {(c.system_prompt ?? "").slice(0, 160)}…
                    </p>
                    <p className="mb-1 font-mono text-[9px] uppercase tracking-wide text-muted-foreground">
                      Assign to role:
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {roleList.map((r) => {
                        const already = held.includes(r);
                        return (
                          <Button
                            key={r}
                            size="sm"
                            variant={already ? "secondary" : "outline"}
                            className="h-6 px-1.5 text-[10px]"
                            onClick={() => {
                              onAssign(r, c.id);
                              setOpenId(null);
                            }}
                          >
                            {already ? `✓ ${r}` : `+ ${r}`}
                          </Button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
        {filtered.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">No matches.</p>
        )}
      </CardContent>
    </Card>
  );
}

"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Network, Plus, Trash2 } from "lucide-react";

export type Team = { id: string; name: string; charter: string; rooms?: number };

export function TeamsCard({
  tokenQS,
  teams,
  onChanged,
}: {
  tokenQS: () => string;
  teams: Team[];
  onChanged: () => void;
}) {
  const [name, setName] = useState("");
  const [charter, setCharter] = useState("");
  const [busy, setBusy] = useState(false);

  async function call(method: string, body?: unknown, qs = "") {
    setBusy(true);
    try {
      await fetch(`/api/business/teams${qs}`, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Network className="h-4 w-4" /> Teams
          {teams.length > 0 && (
            <span className="text-xs text-muted-foreground">({teams.length})</span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-3 flex flex-col gap-2 sm:flex-row">
          <Input
            className="h-8 flex-1 text-sm"
            placeholder="Team name — e.g. Billing Squad"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input
            className="h-8 flex-[1.5] text-sm"
            placeholder="Charter — what this team owns"
            value={charter}
            onChange={(e) => setCharter(e.target.value)}
          />
          <Button
            size="sm"
            disabled={!name.trim() || busy}
            onClick={async () => {
              await call("POST", { name, charter });
              setName(""), setCharter("");
            }}
          >
            <Plus className="h-4 w-4" /> Found
          </Button>
        </div>

        {teams.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No teams yet. Teams are the industry layer — each owns projects, rooms,
            and its own memory footprint.
          </p>
        ) : (
          <div className="space-y-2">
            {teams.map((t) => (
              <div
                key={t.id}
                className="flex items-start justify-between gap-3 rounded-lg border p-3"
              >
                <div className="min-w-0">
                  <span className="text-sm font-medium">{t.name}</span>
                  <span className="ml-2 rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                    {t.rooms ?? 0} rooms
                  </span>
                  {t.charter && (
                    <p className="mt-1 truncate text-xs text-muted-foreground">{t.charter}</p>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Delete ${t.name}`}
                  className="h-7 shrink-0 px-1.5 text-destructive"
                  onClick={() => call("DELETE", undefined, `?id=${t.id}`)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

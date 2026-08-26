"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Network, Plus, Trash2, Users, Zap } from "lucide-react";

export type TeamRole = "lead" | "pm" | "engineer" | "researcher" | "judge";

export type Team = {
  id: string;
  name: string;
  workspace: string;
  selection_mode: "round_robin" | "random" | "manual";
  roles: Record<TeamRole, string[]>;
  skills?: string[];
};

export type Orchestrator = {
  character: string;
  mode: string;
  team_selection: string;
};

export type TeamsConfig = {
  teams: Team[];
  orchestrator: Orchestrator;
};

const ROLE_LABELS: Record<TeamRole, string> = {
  lead: "Lead",
  pm: "PM",
  engineer: "Engineer",
  researcher: "Researcher",
  judge: "Judge",
};

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
  const [workspace, setWorkspace] = useState("~/");
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

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

  async function routeGoal(goal: string) {
    setBusy(true);
    try {
      const res = await fetch("/api/business/orchestrator", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal }),
      });
      const data = await res.json();
      if (data.ok) {
        alert(`Routing: ${data.routing.reasoning}\n\nTeams: ${data.routing.team_ids.join(", ")}\n\nMaster Plan:\n${data.master_plan}`);
      }
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
        {/* Quick route */}
        <div className="mb-3 flex flex-col gap-2 sm:flex-row">
          <Input
            className="h-8 flex-1 text-sm"
            placeholder="Enter a goal to route to teams..."
            onKeyDown={(e) => {
              if (e.key === "Enter" && !busy) {
                routeGoal((e.target as HTMLInputElement).value);
                (e.target as HTMLInputElement).value = "";
              }
            }}
          />
          <Button
            size="sm"
            variant="secondary"
            disabled={busy}
            onClick={() => {
              const input = document.querySelector<HTMLInputElement>("[placeholder*='goal']");
              if (input?.value) routeGoal(input.value);
            }}
          >
            <Zap className="h-4 w-4" /> Route
          </Button>
        </div>

        {/* Create team */}
        <div className="mb-3 flex flex-col gap-2 sm:flex-row">
          <Input
            className="h-8 flex-1 text-sm"
            placeholder="Team name — e.g. Platform"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input
            className="h-8 flex-[1.5] font-mono text-xs"
            placeholder="~/path/to/workspace"
            value={workspace}
            onChange={(e) => setWorkspace(e.target.value)}
          />
          <Button
            size="sm"
            disabled={!name.trim() || busy}
            onClick={async () => {
              await call("POST", { name, workspace });
              setName("");
              setWorkspace("~/");
            }}
          >
            <Plus className="h-4 w-4" /> Create
          </Button>
        </div>

        {/* Team list */}
        {teams.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No teams yet. Teams organize your AI workforce into specialized groups.
          </p>
        ) : (
          <div className="space-y-2">
            {teams.map((t) => (
              <div
                key={t.id}
                className="rounded-lg border p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{t.name}</span>
                      <Badge variant="outline" className="text-[10px]">
                        {t.selection_mode}
                      </Badge>
                      <Badge variant="secondary" className="text-[10px]">
                        {Object.values(t.roles).flat().length} members
                      </Badge>
                    </div>
                    <code className="mt-1 block font-mono text-[10px] text-muted-foreground">
                      {t.workspace}
                    </code>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-xs"
                      onClick={() => setExpanded(expanded === t.id ? null : t.id)}
                    >
                      <Users className="h-3 w-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`Delete ${t.name}`}
                      className="h-6 px-1.5 text-destructive"
                      onClick={() => call("DELETE", undefined, `?id=${t.id}`)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>

                {/* Expanded roles view */}
                {expanded === t.id && (
                  <div className="mt-3 space-y-2 border-t pt-3">
                    {(Object.entries(t.roles) as [TeamRole, string[]][]).map(([role, members]) => (
                      <div key={role} className="flex items-center gap-2 text-xs">
                        <span className="w-20 text-muted-foreground">{ROLE_LABELS[role]}:</span>
                        <div className="flex flex-wrap gap-1">
                          {members.length === 0 ? (
                            <span className="text-muted-foreground">empty</span>
                          ) : (
                            members.map((id) => (
                              <Badge key={id} variant="outline" className="text-[10px]">
                                {id}
                              </Badge>
                            ))
                          )}
                        </div>
                      </div>
                    ))}
                    {t.skills && t.skills.length > 0 && (
                      <div className="flex items-center gap-2 text-xs">
                        <span className="w-20 text-muted-foreground">Skills:</span>
                        <div className="flex flex-wrap gap-1">
                          {t.skills.map((s) => (
                            <Badge key={s} variant="secondary" className="text-[10px]">
                              {s}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <p className="mt-3 text-xs text-muted-foreground">
          Teams organize roles into specialized groups. Use the Route button to send goals to the orchestrator, which selects the right team(s).
        </p>
      </CardContent>
    </Card>
  );
}

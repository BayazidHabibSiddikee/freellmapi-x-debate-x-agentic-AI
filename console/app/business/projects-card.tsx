"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { FolderKanban, Plus, Trash2, Radio } from "lucide-react";
import { Avatar, type Character } from "./avatar";
import type { ProjectAssignment } from "@/lib/business";

export type Project = {
  id: string;
  name: string;
  folder: string;
  assignments: ProjectAssignment[];
  created_at?: string;
};

const ROLE_OPTIONS = [
  "CTO", "PM", "Judge", "Researcher", "Engineer", "Analyst", "Member",
] as const;

export function ProjectsCard({
  tokenQS,
  characters,
  projects,
  activeId,
  onChanged,
}: {
  tokenQS: () => string;
  characters: Character[];
  projects: Project[];
  activeId: string | null;
  onChanged: () => void;
}) {
  const [name, setName] = useState("");
  const [folder, setFolder] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [assigning, setAssigning] = useState<string | null>(null); // project id w/ open assign panel
  const [pickChar, setPickChar] = useState("");
  const [pickRole, setPickRole] = useState<string>("Member");

  const charById = Object.fromEntries(characters.map((c) => [c.id, c]));

  async function call(method: string, body?: unknown, qs = "") {
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch(`/api/business/projects${qs}`, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error ?? `HTTP ${res.status}`);
      onChanged();
      return true;
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "failed");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function setActive(id: string | null) {
    await fetch(`/api/business/settings`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active_project: id }),
    });
    onChanged();
  }

  async function addAssignment(project: Project) {
    if (!pickChar) return;
    const assignments = [
      ...project.assignments.filter((a) => a.character_id !== pickChar),
      { character_id: pickChar, role: pickRole as ProjectAssignment["role"] },
    ];
    const ok = await call("POST", {
      id: project.id,
      name: project.name,
      folder: project.folder,
      assignments,
    });
    if (ok) {
      setAssigning(null);
      setPickChar("");
    }
  }

  async function removeAssignment(project: Project, characterId: string) {
    await call("POST", {
      id: project.id,
      name: project.name,
      folder: project.folder,
      assignments: project.assignments.filter((a) => a.character_id !== characterId),
    });
  }

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <FolderKanban className="h-4 w-4" /> Projects
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* Create form */}
        <div className="mb-3 flex flex-col gap-2 sm:flex-row">
          <Input
            className="h-8 flex-1 text-sm"
            placeholder="Project name — e.g. Billing v2"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input
            className="h-8 flex-[1.5] font-mono text-xs"
            placeholder="~/path/to/project/folder"
            value={folder}
            onChange={(e) => setFolder(e.target.value)}
          />
          <Button
            size="sm"
            disabled={!name.trim() || !folder.trim() || busy}
            onClick={async () => {
              if (await call("POST", { name, folder })) setName(""), setFolder("");
            }}
          >
            <Plus className="h-4 w-4" /> Create
          </Button>
        </div>
        {msg && <p className="mb-2 text-xs text-destructive">{msg}</p>}

        {/* Project list */}
        {projects.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No projects yet. A project binds a folder under <code>~/</code> to a team of
            characters — debates focus on it and dispatched agents work inside it.
          </p>
        ) : (
          <div className="space-y-3">
            {projects.map((p) => {
              const isActive = p.id === activeId;
              return (
                <div
                  key={p.id}
                  className={`rounded-lg border p-3 ${
                    isActive ? "border-[hsl(var(--accent-base))]" : ""
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    {isActive && (
                      <Badge className="gap-1 text-[10px]">
                        <Radio className="h-3 w-3 animate-pulse" /> ACTIVE
                      </Badge>
                    )}
                    <span className="text-sm font-medium">{p.name}</span>
                    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">
                      {p.folder}
                    </code>
                    <span className="ml-auto flex items-center gap-1">
                      {!isActive && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2 text-xs"
                          disabled={busy}
                          onClick={() => setActive(p.id)}
                        >
                          Set active
                        </Button>
                      )}
                      {isActive && (
                        <Button
                          variant="secondary"
                          size="sm"
                          className="h-7 px-2 text-xs"
                          onClick={() => setActive(null)}
                        >
                          Deactivate
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={`Delete ${p.name}`}
                        className="h-7 px-1.5 text-destructive"
                        onClick={() => call("DELETE", undefined, `?id=${p.id}`)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </span>
                  </div>

                  {/* Team */}
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {p.assignments.map((a) => {
                      const c = charById[a.character_id];
                      return (
                        <span
                          key={a.character_id}
                          className="inline-flex items-center gap-1 rounded-full border py-0.5 pl-0.5 pr-1.5 text-xs"
                        >
                          <Avatar
                            name={c?.name ?? a.character_id}
                            id={a.character_id}
                            className="h-5 w-5"
                            textClass="text-[8px]"
                          />
                          <span className="max-w-28 truncate">{c?.name ?? a.character_id}</span>
                          <Badge variant="outline" className="px-1 text-[9px]">
                            {a.role}
                          </Badge>
                          <button
                            aria-label="Remove from project"
                            className="rounded-full p-0.5 hover:bg-muted"
                            onClick={() => removeAssignment(p, a.character_id)}
                          >
                            ×
                          </button>
                        </span>
                      );
                    })}
                    {assigning === p.id ? (
                      <span className="inline-flex items-center gap-1">
                        <select
                          aria-label="Character"
                          value={pickChar}
                          onChange={(e) => setPickChar(e.target.value)}
                          className="rounded border bg-transparent px-1 py-0.5 text-xs"
                        >
                          <option value="">character…</option>
                          {characters.map((c) => (
                            <option key={c.id} value={c.id}>{c.name}</option>
                          ))}
                        </select>
                        <select
                          aria-label="Project role"
                          value={pickRole}
                          onChange={(e) => setPickRole(e.target.value)}
                          className="rounded border bg-transparent px-1 py-0.5 text-xs"
                        >
                          {ROLE_OPTIONS.map((r) => (
                            <option key={r} value={r}>{r}</option>
                          ))}
                        </select>
                        <Button size="sm" className="h-6 px-2 text-[10px]" onClick={() => addAssignment(p)}>
                          Add
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-1 text-[10px]"
                          onClick={() => setAssigning(null)}
                        >
                          ✕
                        </Button>
                      </span>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs"
                        onClick={() => setAssigning(p.id)}
                      >
                        + assign character
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        <p className="mt-3 text-xs text-muted-foreground">
          When a project is ACTIVE: debates speak through the project&apos;s team (round-robin),
          the discussion is framed around its folder, and dispatched subtasks land in that folder.
        </p>
      </CardContent>
    </Card>
  );
}

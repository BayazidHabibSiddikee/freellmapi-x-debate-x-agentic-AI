import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import { getTeamsConfig, saveTeamsConfig, getTeam, getTeamMembers, type Team, type TeamRole } from "@/lib/business";

export async function GET(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const config = getTeamsConfig();
  return NextResponse.json(config);
}

type TeamBody = {
  id?: string;
  name?: string;
  workspace?: string;
  selection_mode?: "round_robin" | "random" | "manual";
  roles?: Record<TeamRole, string[]>;
  skills?: string[];
};

export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: TeamBody;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }

  if (!body.name?.trim()) {
    return NextResponse.json({ error: "name is required" }, { status: 400 });
  }

  const config = getTeamsConfig();
  const id = body.id ?? `team_${Date.now().toString(36)}`;

  const team: Team = {
    id,
    name: body.name.trim(),
    workspace: body.workspace ?? "~/",
    selection_mode: body.selection_mode ?? "round_robin",
    roles: body.roles ?? { lead: [], pm: [], engineer: [], researcher: [], judge: [] },
    skills: body.skills ?? [],
  };

  const idx = config.teams.findIndex((t) => t.id === id);
  if (idx >= 0) config.teams[idx] = team;
  else config.teams.push(team);

  saveTeamsConfig(config);
  return NextResponse.json({ ok: true, team });
}

export async function DELETE(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const id = req.nextUrl.searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id is required" }, { status: 400 });

  const config = getTeamsConfig();
  const next = config.teams.filter((t) => t.id !== id);
  if (next.length === config.teams.length) {
    return NextResponse.json({ error: "team not found" }, { status: 404 });
  }

  config.teams = next;
  saveTeamsConfig(config);
  return NextResponse.json({ ok: true });
}

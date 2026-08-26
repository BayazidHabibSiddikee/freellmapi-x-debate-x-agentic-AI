import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import {
  listCharacters,
  getRoles,
  getSettings,
  getProjects,
  BUSINESS_ROLES,
  ROLE_PROMPTS,
} from "@/lib/business";

async function fetchTeams(): Promise<unknown[]> {
  try {
    const res = await fetch(
      `${process.env.AGENT_TOOLS_URL ?? "http://127.0.0.1:5090"}/teams`,
      { signal: AbortSignal.timeout(4_000) },
    );
    if (!res.ok) return [];
    return (await res.json()).teams ?? [];
  } catch {
    return [];
  }
}

export async function GET(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const roles = getRoles();
  // Shape for the UI: role → { members: string[], workspace }
  const shaped = Object.fromEntries(
    Object.entries(roles).map(([r, cfg]) => [r, cfg]),
  );
  return NextResponse.json({
    characters: listCharacters(),
    roles: shaped,
    role_list: BUSINESS_ROLES,
    role_prompts: ROLE_PROMPTS,
    settings: getSettings(),
    projects: getProjects(),
    teams: await fetchTeams(),
  });
}

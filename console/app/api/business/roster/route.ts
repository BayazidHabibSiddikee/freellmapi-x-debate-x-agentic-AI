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
  });
}

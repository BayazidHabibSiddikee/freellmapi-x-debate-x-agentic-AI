import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import { assignRole, getCharacter, getRoles } from "@/lib/business";

type Body = {
  role?: string;
  /** Replace the full member list */
  set_members?: string[];
  /** Add member(s) */
  add?: string | string[];
  /** Remove member(s) */
  remove?: string | string[];
  /** Set (or clear with null/"") the role's workspace directory under ~ */
  workspace?: string | null;
};

export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: Body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }

  const role = body.role;
  if (!role) return NextResponse.json({ error: "role is required" }, { status: 400 });

  const toArr = (v: string | string[] | undefined) =>
    v === undefined ? undefined : Array.isArray(v) ? v : [v];

  try {
    // Validate ids early for clearer errors
    const ids = [...(toArr(body.add) ?? []), ...(body.set_members ?? [])];
    for (const id of ids) {
      if (!getCharacter(id)) {
        return NextResponse.json({ error: `unknown character: ${id}` }, { status: 400 });
      }
    }
    const roles = assignRole({
      role,
      add: toArr(body.add),
      remove: toArr(body.remove),
      setMembers: body.set_members,
      workspace: body.workspace === "" ? null : body.workspace,
    });
    return NextResponse.json({ ok: true, roles });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "assign failed" },
      { status: 400 },
    );
  }
}

export async function GET(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  return NextResponse.json({ roles: getRoles() });
}

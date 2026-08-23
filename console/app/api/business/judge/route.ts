import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import { getRoles, activeProject } from "@/lib/business";

const AGENT_URL = process.env.AGENT_TOOLS_URL ?? "http://localhost:5090";

export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: { topic?: string; history?: Array<{ speaker: string; text: string }> };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }
  if (!body.topic?.trim()) {
    return NextResponse.json({ error: "topic is required" }, { status: 400 });
  }

  // Hint the judge with each role's pinned workspace
  const roles = getRoles();
  const workspaces: Record<string, string> = Object.fromEntries(
    Object.entries(roles)
      .filter(([, cfg]) => cfg.workspace && cfg.members.length > 0)
      .map(([r, cfg]) => [r, cfg.workspace as string]),
  );

  // Active project folder takes priority as the dispatch target
  const project = activeProject();
  if (project) {
    workspaces["active project"] = project.folder;
  }

  try {
    const res = await fetch(`${AGENT_URL}/judge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...body, workspaces }),
      signal: AbortSignal.timeout(300_000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.ok ? 200 : 502 });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "judge unreachable" },
      { status: 503 },
    );
  }
}

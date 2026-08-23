import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import { getCharacter } from "@/lib/business";

const AGENT_URL = process.env.AGENT_TOOLS_URL ?? "http://localhost:5090";

export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: { role?: string; tool?: string; args?: Record<string, unknown>; character_id?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }
  if (!body.tool) return NextResponse.json({ error: "tool is required" }, { status: 400 });

  // Per-person grants from their persona file (config/business/personas/<id>.md)
  const personaTools = body.character_id ? getCharacter(body.character_id)?.tools ?? [] : [];

  try {
    const res = await fetch(`${AGENT_URL}/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tool: body.tool,
        args: body.args ?? {},
        role: body.role,
        allowed: personaTools,
      }),
      // downloads + ingestion can be slow
      signal: AbortSignal.timeout(600_000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.ok ? 200 : 502 });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "tool execution failed" },
      { status: 503 },
    );
  }
}

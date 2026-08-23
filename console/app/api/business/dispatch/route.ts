import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";

const AGENT_URL = process.env.AGENT_TOOLS_URL ?? "http://127.0.0.1:5090";

export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: { spec?: Record<string, unknown>; only?: string[] };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }
  if (!body.spec || !Array.isArray(body.spec.subtasks)) {
    return NextResponse.json({ error: "spec with subtasks is required" }, { status: 400 });
  }

  try {
    // Coding agents can run for a long time per subtask
    const res = await fetch(`${AGENT_URL}/dispatch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(3_600_000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.ok ? 200 : 502 });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "dispatch failed" },
      { status: 503 },
    );
  }
}

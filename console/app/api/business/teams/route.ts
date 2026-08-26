import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";

const AGENT_URL = process.env.AGENT_TOOLS_URL ?? "http://127.0.0.1:5090";

export async function GET(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  try {
    const res = await fetch(`${AGENT_URL}/teams`, { signal: AbortSignal.timeout(5_000) });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ teams: [], error: "agent store unreachable" });
  }
}

export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  try {
    const body = await req.json();
    const res = await fetch(`${AGENT_URL}/teams`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await res.json());
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "failed" },
      { status: 502 },
    );
  }
}

export async function DELETE(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const id = req.nextUrl.searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id is required" }, { status: 400 });
  try {
    await fetch(`${AGENT_URL}/teams/${encodeURIComponent(id)}`, {
      method: "DELETE",
      signal: AbortSignal.timeout(5_000),
    });
    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "failed" },
      { status: 502 },
    );
  }
}

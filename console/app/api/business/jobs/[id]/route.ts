import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";

const AGENT_URL = process.env.AGENT_TOOLS_URL ?? "http://127.0.0.1:5090";

type Params = { params: Promise<{ id: string }> };

export async function GET(_req: NextRequest, p: Params) {
  if (!validateToken(_req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const { id } = await p.params;
  try {
    const res = await fetch(`${AGENT_URL}/jobs/${encodeURIComponent(id)}`, {
      signal: AbortSignal.timeout(8_000),
    });
    return NextResponse.json(await res.json());
  } catch (err) {
    return NextResponse.json(
      { ok: false, error: err instanceof Error ? err.message : "job unreachable" },
      { status: 502 },
    );
  }
}

export async function POST(_req: NextRequest, p: Params) {
  if (!validateToken(_req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const { id } = await p.params;
  try {
    const res = await fetch(`${AGENT_URL}/jobs/${encodeURIComponent(id)}/cancel`, {
      method: "POST",
      signal: AbortSignal.timeout(8_000),
    });
    return NextResponse.json(await res.json());
  } catch (err) {
    return NextResponse.json(
      { ok: false, error: err instanceof Error ? err.message : "cancel failed" },
      { status: 502 },
    );
  }
}
import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";

const AGENT_URL = process.env.AGENT_TOOLS_URL ?? "http://localhost:5090";

export async function GET(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const role = req.nextUrl.searchParams.get("role") ?? "";
  try {
    const res = await fetch(`${AGENT_URL}/tools?role=${encodeURIComponent(role)}`, {
      signal: AbortSignal.timeout(5_000),
    });
    if (!res.ok) throw new Error(`agent returned ${res.status}`);
    return NextResponse.json(await res.json());
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "agent tools unreachable" },
      { status: 503 },
    );
  }
}

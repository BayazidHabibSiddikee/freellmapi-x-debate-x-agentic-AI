import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";

const AGENT_URL = process.env.AGENT_TOOLS_URL ?? "http://127.0.0.1:5090";

export async function GET(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const limit = req.nextUrl.searchParams.get("limit") ?? "30";
  try {
    const res = await fetch(`${AGENT_URL}/jobs?limit=${encodeURIComponent(limit)}`, {
      signal: AbortSignal.timeout(8_000),
    });
    return NextResponse.json(await res.json());
  } catch (err) {
    return NextResponse.json(
      { ok: false, error: err instanceof Error ? err.message : "queue unreachable" },
      { status: 502 },
    );
  }
}

type Body = {
  spec?: Record<string, unknown>;
  project?: Record<string, unknown>;
  target_repo?: string;
};

export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: Body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }
  if (!body.spec || !Array.isArray(body.spec.subtasks) || (body.spec.subtasks as unknown[]).length === 0) {
    return NextResponse.json(
      { ok: false, error: "spec with subtasks is required" },
      { status: 400 },
    );
  }

  try {
    // Creating a job returns immediately; subtasks run in the background pool.
    const res = await fetch(`${AGENT_URL}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        spec: body.spec,
        project: body.project ?? {},
        target_repo: body.target_repo ?? "",
      }),
      signal: AbortSignal.timeout(15_000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.ok ? 200 : 502 });
  } catch (err) {
    return NextResponse.json(
      { ok: false, error: err instanceof Error ? err.message : "enqueue failed" },
      { status: 503 },
    );
  }
}
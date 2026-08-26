import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";

const RAG_URL = process.env.RAG_SERVER_URL ?? "http://127.0.0.1:5080";

type Body = { topic?: string; history?: Array<{ speaker: string; text: string }> };

/** POST {topic, history} → render boardroom transcript → ingest into hybrid RAG */
export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: Body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }
  const topic = body.topic?.trim();
  const history = body.history ?? [];
  if (!topic || history.length === 0) {
    return NextResponse.json({ error: "topic and history are required" }, { status: 400 });
  }

  const slug = topic.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 40);
  const fname = `boardroom_${new Date().toISOString().slice(0, 10)}_${slug}.md`;

  let md = `# Boardroom decision — ${topic}\n\n`;
  md += `**Date:** ${new Date().toISOString()}\n`;
  md += `**Participants:** ${[...new Set(history.map((h) => h.speaker))].join(", ")}\n\n---\n\n`;
  for (const t of history) {
    md += `**[${t.speaker}]**: ${t.text}\n\n`;
  }

  try {
    const form = new FormData();
    form.append("file", new Blob([md], { type: "text/markdown" }), fname);
    const res = await fetch(`${RAG_URL}/upload/doc`, {
      method: "POST",
      body: form,
      signal: AbortSignal.timeout(120_000),
    });
    const data = await res.json();
    if (!res.ok || data.ok === false) {
      throw new Error(data.message ?? data.error ?? `RAG returned ${res.status}`);
    }
    return NextResponse.json({
      ok: true,
      file: fname,
      chars: md.length,
      message: `Debate ingested as "${fname}" — future debates can cite it.`,
    });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "ingest failed" },
      { status: 502 },
    );
  }
}

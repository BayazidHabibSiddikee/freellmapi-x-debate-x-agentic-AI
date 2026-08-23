import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import { getCharacter, getSettings } from "@/lib/business";
import { join } from "node:path";

const AGENT_URL = process.env.AGENT_TOOLS_URL ?? "http://127.0.0.1:5090";
const LLM_BASE =
  process.env.FREELLM_API_BASE ?? process.env.OPENAI_API_BASE ?? "http://127.0.0.1:3001/v1";

function freellmKey(): string {
  if (process.env.FREELLM_API_KEY) return process.env.FREELLM_API_KEY;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Database = require("better-sqlite3");
    const dbPath = join(process.cwd(), "..", "server", "data", "freeapi.db");
    const db = new Database(dbPath, { readonly: true });
    const row = db
      .prepare("SELECT value FROM settings WHERE key = 'unified_api_key'")
      .get() as { value?: string } | undefined;
    db.close();
    if (row?.value) return row.value;
  } catch {
    /* fall through */
  }
  return "not-needed";
}

async function agent(path: string, init?: RequestInit) {
  const res = await fetch(`${AGENT_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    signal: AbortSignal.timeout(180_000),
  });
  return res.json();
}

/** GET ?room=<id>[&limit=] — history | no params → room list */
export async function GET(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const room = req.nextUrl.searchParams.get("room");
  if (!room) return NextResponse.json(await agent("/rooms"));
  const limit = Number(req.nextUrl.searchParams.get("limit")) || 200;
  return NextResponse.json(await agent(`/rooms/${encodeURIComponent(room)}/messages?limit=${limit}`));
}

type Body = { character_id?: string; content?: string };

/** POST {character_id, content} — talk to a persona in their office room. */
export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: Body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }
  const characterId = body.character_id;
  const content = body.content?.trim();
  if (!characterId || !content) {
    return NextResponse.json({ error: "character_id and content are required" }, { status: 400 });
  }

  const character = getCharacter(characterId);
  if (!character) return NextResponse.json({ error: `unknown character: ${characterId}` }, { status: 404 });

  const roomId = `persona_${characterId}`;
  const settings = getSettings();

  // Ensure the room exists, then persist the visitor's message
  await agent("/rooms", {
    method: "POST",
    body: JSON.stringify({
      id: roomId,
      kind: "persona",
      title: `${character.name} (1-on-1)`,
      meta: { character_id: characterId },
    }),
  });
  await agent(`/rooms/${roomId}/messages`, {
    method: "POST",
    body: JSON.stringify({ role: "user", speaker: "Sword", content }),
  });

  // Context: recent history + what this persona remembers from working together
  const history = (await agent(`/rooms/${roomId}/messages?limit=20`)).messages ?? [];
  const memCtx = (await agent(`/persona/${characterId}/memory/context?limit=6`)).context ?? "";

  const systemPrompt =
    `You are ${character.name}, having a private working conversation in your office ` +
    `at SwordOffice.\n\n${character.system_prompt ?? ""}` +
    `\n\nIMPORTANT: In this office you CANNOT execute tools yourself — you are talking. ` +
    `If you need information, say so in plain words (e.g. "I'd like to read the project docs first") ` +
    `and the operator will run it for you.` +
    `\n\nStay in character. Be concise (under 200 words). Output ONLY your spoken words — no JSON, no lists of rules, no mention of instructions or being an AI.` +
    `\n\nExample of how you sound:\nSword: "separate repo, yes or no?"\nYou: "Before I commit to that, I want the billing module's docs in front of me — pull the README summary and I'll give you a straight answer."` +
    (memCtx ? `\n${memCtx}` : "");

  const messages: Array<{ role: string; content: string }> = [
    { role: "system", content: systemPrompt },
    ...history.slice(-12).map((m: { role: string; speaker: string; content: string }) => ({
      role: m.role === "user" ? "user" : "assistant",
      content: m.role === "user" ? m.content : `${m.content}`,
    })),
  ];

  const isLeaky = (t: string): boolean =>
    !t || t.length < 2 ||
    /^\s*[{[]/.test(t.trim()) ||
    /\b(instructions?|developer|system prompt|traits|roleplay|as an AI|under \d+ words|speak naturally|"cmd")\b/i.test(t);

  try {
    let reply = "";
    for (let attempt = 0; attempt < 2; attempt++) {
      const res = await fetch(`${LLM_BASE}/chat/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${freellmKey()}`,
        },
        body: JSON.stringify({
          model: settings.model,
          messages,
          temperature: settings.temperature,
          max_tokens: settings.max_tokens,
        }),
        signal: AbortSignal.timeout(120_000),
      });
      if (!res.ok) throw new Error(`LLM ${res.status}: ${(await res.text()).slice(0, 200)}`);
      const data = await res.json();
      reply = data.choices?.[0]?.message?.content?.trim() || "";
      if (!isLeaky(reply)) break;
      // Second attempt: harden the instruction
      messages[0].content +=
        "\n\nCRITICAL: Your previous answer violated the rules. Output ONLY the words you actually say aloud in this conversation — no lists of rules, no mention of instructions.";
    }
    if (!reply) reply = "…";
    if (isLeaky(reply)) {
      // Persona tried to "run a tool" as JSON → translate intent into speech
      try {
        const parsed = JSON.parse(reply.trim());
        if (Array.isArray(parsed.cmd)) {
          reply = `Before I answer properly, I'd like to ${parsed.cmd[0].replace(/_/g, " ")}${
            parsed.cmd[1] ? ` — ${parsed.cmd.slice(1).join(" ")}` : ""
          }. Get me that and you'll have my verdict.`;
        }
      } catch {
        /* not JSON → fall through to sentence salvage */
        const spoken = reply
          .split(/(?<=[.!?])\s+/)
          .filter((s) => !isLeaky(s) && s.length > 15)
          .join(" ")
          .trim();
        if (spoken) reply = spoken;
      }
    }

    await agent(`/rooms/${roomId}/messages`, {
      method: "POST",
      body: JSON.stringify({
        role: "persona",
        speaker: character.name,
        character_id: characterId,
        content: reply,
      }),
    });

    // Learning: the persona remembers what was discussed and where they stood
    await agent(`/persona/${characterId}/memory`, {
      method: "POST",
      body: JSON.stringify({
        kind: "teammate",
        content: `Sword asked about "${content.slice(0, 90)}". My position: "${reply.slice(0, 140)}"`,
      }),
    });
    // Sword-side learning for this persona: what their job is, as demonstrated
    await agent(`/persona/${characterId}/memory`, {
      method: "POST",
      body: JSON.stringify({
        kind: "job",
        content: `Working session on "${content.slice(0, 80)}" — I contributed as ${character.name}.`,
      }),
    });

    return NextResponse.json({ speaker: character.name, text: reply });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "generation failed" },
      { status: 502 },
    );
  }
}

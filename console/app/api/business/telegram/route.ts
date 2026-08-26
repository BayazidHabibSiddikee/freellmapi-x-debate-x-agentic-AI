import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import { getSettings, type TelegramBotEntry } from "@/lib/business";

/**
 * POST /api/business/telegram/send
 *
 * Trigger an urgent alert message through a configured bot to its allowed chats.
 * Called by: agent tool `urgent_alert`, or manually from the console.
 *
 * Body:
 *   message   — required, under 2000 chars
 *   bot_name  — optional: specific bot to use (id field)
 *   team      — optional context tag included in the payload
 */
export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: { message?: string; bot_name?: string; team?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }

  const message = (body.message || "").trim();
  if (!message) return NextResponse.json({ error: "message is required" }, { status: 400 });

  const settings = getSettings();
  const bots: TelegramBotEntry[] = settings.telegram_bots || [];
  const targetBot = bots.find((b) => b.id === body.bot_name);
  const activeBots: TelegramBotEntry[] = targetBot ? [targetBot] : bots.filter((b) => b.active !== false);

  if (!activeBots.length) {
    return NextResponse.json({ error: "no active telegram bots configured" }, { status: 400 });
  }

  // Each bot's token — build minimal dispatch payloads
  const AGENT_TOOLS_URL = process.env.AGENT_TOOLS_URL ?? "http://127.0.0.1:5090";
  const results: Array<{ bot: string; sent: boolean; err?: string }> = [];

  for (const bot of activeBots) {
    if (!bot.bot_token) {
      results.push({ bot: bot.name, sent: false, err: "missing token" });
      continue;
    }
    // Forward as a tool call so the agent-side logic handles routing
    try {
      const res = await fetch(`${AGENT_TOOLS_URL}/tools/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tool: "urgent_alert",
          args: {
            message,
            team: body.team,
            receiver_emails: [],
          },
          role: "System",
        }),
        signal: AbortSignal.timeout(10_000),
      });
      const data = await res.json().catch(() => null);
      results.push({ bot: bot.name, sent: !!(data?.ok), err: data?.error });
    } catch (err) {
      results.push({ bot: bot.name, sent: false, err: String(err) });
    }
  }

  const sentCount = results.filter((r) => r.sent).length;
  return NextResponse.json({ delivered: sentCount, total: results.length, results });
}

/** GET /api/business/telegram/bots — list configured bot names/ids (no tokens). */
export async function GET(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const settings = getSettings();
  const bots: TelegramBotEntry[] = settings.telegram_bots || [];
  return NextResponse.json({
    bots: bots.map((b) => ({ id: b.id, name: b.name, owner: b.owner_email, active: b.active !== false })),
    count: bots.length,
  });
}

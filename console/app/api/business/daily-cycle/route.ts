import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import { getTeamsConfig, getTeam, type Team } from "@/lib/business";

const API_BASE = process.env.FREELLM_API_BASE ?? process.env.OPENAI_API_BASE ?? "http://127.0.0.1:3001";

/** POST: Trigger daily cycle for one or all teams. */
export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: { team_id?: string; run_all?: boolean };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }

  const config = getTeamsConfig();
  if (!config.teams.length) {
    return NextResponse.json({ error: "no teams configured" }, { status: 400 });
  }

  // Delegate to the server-side scheduler which uses the shared module
  try {
    const endpoint = `${API_BASE}:3001/api/daily-cycle`;
    const payload = body.run_all
      ? { run_all: true }
      : { team_id: body.team_id };

    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(300_000), // 5 min timeout for long cycles
    });

    if (!res.ok) {
      const err = await res.text();
      return NextResponse.json({ error: `Server error: ${err}` }, { status: 502 });
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (err) {
    // If server endpoint not available, run locally (fallback for dev)
    console.warn("[daily-cycle] Server endpoint unavailable, running locally");

    if (body.run_all) {
      const teams = config.teams.filter(t => t.daily_cycle?.enabled);
      const results = [];
      for (const team of teams) {
        const result = await runLocalDailyCycle(team);
        results.push(result);
      }
      return NextResponse.json({ ok: true, results, source: "local" });
    } else if (body.team_id) {
      const team = getTeam(body.team_id);
      if (!team) return NextResponse.json({ error: "team not found" }, { status: 404 });
      const result = await runLocalDailyCycle(team);
      return NextResponse.json({ ok: true, results: [result], source: "local" });
    } else {
      return NextResponse.json({ error: "team_id or run_all required" }, { status: 400 });
    }
  }
}

/** GET: Check daily cycle status. */
export async function GET(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const config = getTeamsConfig();
  const teamStatus = config.teams.map(t => ({
    team_id: t.id,
    name: t.name,
    daily_cycle_enabled: t.daily_cycle?.enabled ?? false,
    schedule: t.daily_cycle?.schedule ?? "N/A",
    iterations: t.daily_cycle?.iterations ?? 0,
    auto_commit: t.daily_cycle?.auto_commit ?? false,
    requires_review_panel: t.daily_cycle?.requires_review_panel ?? false,
  }));

  return NextResponse.json({ ok: true, teams: teamStatus });
}

/** Local fallback: simplified daily cycle without the full server module. */
async function runLocalDailyCycle(team: Team): Promise<{ team_id: string; status: string; transcript?: string }> {
  const LLM_BASE = process.env.FREELLM_API_BASE ?? process.env.OPENAI_API_BASE ?? "http://127.0.0.1:3001/v1";

  function freellmKey(): string {
    if (process.env.FREELLM_API_KEY) return process.env.FREELLM_API_KEY;
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const Database = require("better-sqlite3");
      const { join } = require("node:path");
      const dbPath = join(process.cwd(), "..", "server", "data", "freeapi.db");
      const db = new Database(dbPath, { readonly: true });
      const row = db.prepare("SELECT value FROM settings WHERE key = 'unified_api_key'").get() as { value?: string } | undefined;
      db.close();
      if (row?.value) return row.value;
    } catch { /* fall through */ }
    return "not-needed";
  }

  const { writeFile, mkdir } = await import("node:fs/promises");
  const { join } = await import("node:path");

  const dailyCycle = team.daily_cycle;
  if (!dailyCycle?.enabled) {
    return { team_id: team.id, status: "disabled" };
  }

  const members = Object.values(team.roles).flat();
  const memberNames = members.map(id => {
    // Simple name lookup
    const nameMap: Record<string, string> = {
      nova_vance: "Nova Vance", sterling_cole: "Sterling Cole", linus_wolf: "Linus Wolf",
      grace_kim: "Grace Kim", atlas_grey: "Atlas Grey", yuki_tanaka: "Yuki Tanaka",
      dev_okafor: "Dev Okafor", sofia_alvarez: "Sofia Alvarez", iris_lund: "Iris Lund",
      ada_chen: "Ada Chen", marcus_reed: "Marcus Reed", kai_nakamura: "Kai Nakamura",
      ravi_patel: "Ravi Patel", omar_farouk: "Omar Farouk", zoe_martin: "Zoe Martin",
      priya_sharma: "Priya Sharma", tom_becker: "Tom Becker", vera_kline: "Vera Kline",
      theo_planner: "Theo Planner", makima: "Makima", echo: "Echo", openclaw: "OpenClaw",
    };
    return nameMap[id] ?? id;
  }).join(", ");

  const turns: string[] = [];
  const transcriptDir = (team.transcript_dir ?? `~/swordoffice/transcripts/${team.id}`).replace("~", process.env.HOME ?? "/root");
  await mkdir(transcriptDir, { recursive: true });
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filepath = join(transcriptDir, `daily-${timestamp}.md`);

  await writeFile(filepath, `# ${team.name} Daily Cycle\n\n**Date**: ${new Date().toISOString()}\n**Iterations**: ${dailyCycle.iterations}\n\n---\n\n`, "utf-8");

  for (let i = 0; i < dailyCycle.iterations; i++) {
    const isLast = i === dailyCycle.iterations - 1;
    const role = isLast ? "lead/judge" : ["engineer", "researcher", "pm"][i % 3];

    const systemPrompt = isLast
      ? `You are the leader and judge of the "${team.name}" team. Distill the debate into SUMMARY, ACTION_ITEMS, and FLAGGED sections.`
      : `You are a ${role} on the "${team.name}" team. Propose your perspective concisely.`;

    try {
      const res = await fetch(`${LLM_BASE}/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${freellmKey()}` },
        body: JSON.stringify({
          model: "auto",
          messages: [
            { role: "system", content: systemPrompt },
            { role: "user", content: `Turn ${i + 1}/${dailyCycle.iterations}` },
          ],
          temperature: 0.6,
          max_tokens: isLast ? 400 : 200,
        }),
        signal: AbortSignal.timeout(30_000),
      });

      if (res.ok) {
        const data = await res.json() as { choices?: Array<{ message?: { content?: string } }> };
        const text = data.choices?.[0]?.message?.content?.trim() ?? "[no response]";
        turns.push(`**Turn ${i + 1} (${role})**: ${text}`);
      } else {
        turns.push(`**Turn ${i + 1} (${role})**: [LLM error ${res.status}]`);
      }
    } catch {
      turns.push(`**Turn ${i + 1} (${role})**: [timeout]`);
    }

    // Append turn to transcript
    const { appendFileSync } = await import("node:fs");
    appendFileSync(filepath, turns[turns.length - 1] + "\n\n", "utf-8");
  }

  return { team_id: team.id, status: "completed", transcript: filepath };
}

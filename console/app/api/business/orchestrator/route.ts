import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import { getTeamsConfig, getTeam, getTeamMembers, getCharacter, getOrchestrator, getTopJudge, type Team, type TeamRole } from "@/lib/business";
import { writeFile, mkdir } from "node:fs/promises";
import { join } from "node:path";

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

/** Route a goal to appropriate teams using the orchestrator character. */
async function routeGoal(goal: string, teams: Team[]): Promise<{ team_ids: string[]; reasoning: string }> {
  const orchestrator = getOrchestrator();
  const orchestratorChar = getCharacter(orchestrator.character);

  const teamList = teams.map(t => `- ${t.id}: ${t.name} (workspace: ${t.workspace})`).join("\n");

  const systemPrompt = `You are the orchestrator of an AI team. Your job is to route a goal to the appropriate team(s).

Available teams:
${teamList}

Based on the goal, decide which team(s) should handle it. Return JSON:
{
  "team_ids": ["team_id", ...],
  "reasoning": "brief explanation"
}

Rules:
- If the goal is clearly for one domain, route to that single team
- If the goal spans multiple domains, route to all relevant teams
- If uncertain, route to the most likely team
- Always provide reasoning`;

  const res = await fetch(`${LLM_BASE}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${freellmKey()}`,
    },
    body: JSON.stringify({
      model: "auto",
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: goal },
      ],
      temperature: 0.3,
      max_tokens: 300,
    }),
    signal: AbortSignal.timeout(30_000),
  });

  if (!res.ok) {
    return { team_ids: teams.map(t => t.id), reasoning: "LLM unavailable, routing to all teams" };
  }

  const data = await res.json() as { choices?: Array<{ message?: { content?: string } }> };
  const text = data.choices?.[0]?.message?.content?.trim() ?? "";

  try {
    const parsed = JSON.parse(text);
    return {
      team_ids: parsed.team_ids?.filter((id: string) => teams.some(t => t.id === id)) ?? teams.map(t => t.id),
      reasoning: parsed.reasoning ?? "routed by orchestrator",
    };
  } catch {
    return { team_ids: teams.map(t => t.id), reasoning: "parse error, routing to all teams" };
  }
}

/** Run a mini-debate session for a team and collect their spec. */
async function runTeamDebate(goal: string, team: Team): Promise<{ team_id: string; spec: string; members: string[]; turns: string[] }> {
  const members = getTeamMembers(team);
  const memberNames = members.map(id => getCharacter(id)?.name ?? id).join(", ");
  const turns: string[] = [];

  const turnPrompts = [
    { role: "engineer", prompt: "As an engineer on this team, what technical approach would you suggest? Be brief (2-3 sentences)." },
    { role: "researcher", prompt: "As a researcher, what context or prior art should we consider? Be brief (2-3 sentences)." },
    { role: "pm", prompt: "As PM, what are the key requirements and priorities? Be brief (2-3 sentences)." },
    { role: "judge", prompt: "As the judge, synthesize these perspectives into a final team spec. Be concise (under 150 words)." },
  ];

  for (const turn of turnPrompts) {
    const charId = team.roles[turn.role as keyof typeof team.roles]?.[0];
    const char = getCharacter(charId ?? "");
    const charName = char?.name ?? turn.role;

    const systemPrompt = `You are ${charName}, the ${turn.role} of the "${team.name}" team.
Your teammates: ${memberNames}.
Goal: ${goal}

${turn.prompt}`;

    const res = await fetch(`${LLM_BASE}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${freellmKey()}`,
      },
      body: JSON.stringify({
        model: "auto",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: goal },
        ],
        temperature: 0.5,
        max_tokens: 200,
      }),
      signal: AbortSignal.timeout(30_000),
    });

    let text = `${charName} (${turn.role}): [awaiting response]`;
    if (res.ok) {
      const data = await res.json() as { choices?: Array<{ message?: { content?: string } }> };
      text = data.choices?.[0]?.message?.content?.trim() ?? text;
    }

    turns.push(`**${charName} (${turn.role})**: ${text}`);
  }

  const spec = turns[turns.length - 1]; // judge's output is the spec

  return { team_id: team.id, spec, members: memberNames.split(", "), turns };
}

/** Write team debate transcript to markdown. */
async function writeTranscript(team: Team, goal: string, turns: string[]): Promise<string> {
  const transcriptDir = team.transcript_dir ?? `~/swordoffice/transcripts/${team.id}`;
  const expandedDir = transcriptDir.replace("~", process.env.HOME ?? "/root");

  await mkdir(expandedDir, { recursive: true });

  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filename = `debate-${timestamp}.md`;
  const filepath = join(expandedDir, filename);

  const content = `# ${team.name} Debate Transcript

**Goal**: ${goal}
**Date**: ${new Date().toISOString()}

---

${turns.join("\n\n")}

---

*Generated by SwordOffice Multi-Team Orchestrator*
`;

  await writeFile(filepath, content, "utf-8");
  return filepath;
}

/** Collect responses from each team's debate and merge them. */
async function collectTeamSpecs(goal: string, teamIds: string[]): Promise<Array<{ team_id: string; spec: string; members: string[]; transcript: string }>> {
  const results: Array<{ team_id: string; spec: string; members: string[]; transcript: string }> = [];

  for (const teamId of teamIds) {
    const team = getTeam(teamId);
    if (!team) continue;

    const { spec, members, turns } = await runTeamDebate(goal, team);
    const transcript = await writeTranscript(team, goal, turns);

    results.push({ team_id: teamId, spec, members, transcript });
  }

  return results;
}

/** Merge multiple team specs into a master dispatch plan using the top judge. */
async function mergeSpecs(goal: string, teamSpecs: Array<{ team_id: string; spec: string; members: string[]; transcript: string }>): Promise<string> {
  const topJudge = getTopJudge();
  const topJudgeChar = getCharacter(topJudge.character);

  const specsText = teamSpecs.map(ts => {
    const team = getTeam(ts.team_id);
    return `## ${team?.name ?? ts.team_id}\n${ts.spec}`;
  }).join("\n\n");

  const systemPrompt = `You are ${topJudgeChar?.name ?? "Solomon Hart"}, the top-level judge merging specs from multiple teams into a master dispatch plan.

Goal: ${goal}

Team specs:
${specsText}

Produce a unified dispatch plan that:
1. Identifies dependencies between teams
2. Sequences work appropriately
3. Resolves any conflicts or overlaps
4. Lists concrete subtasks with assigned teams

Be concise and actionable (under 500 words).`;

  const res = await fetch(`${LLM_BASE}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${freellmKey()}`,
    },
    body: JSON.stringify({
      model: "auto",
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: "Merge these team specs into a master plan." },
      ],
      temperature: 0.4,
      max_tokens: 800,
    }),
    signal: AbortSignal.timeout(60_000),
  });

  if (!res.ok) return `Master plan:\n\n${specsText}`;
  const data = await res.json() as { choices?: Array<{ message?: { content?: string } }> };
  return data.choices?.[0]?.message?.content?.trim() ?? `Master plan:\n\n${specsText}`;
}

export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: { goal?: string; team_ids?: string[] };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }

  if (!body.goal?.trim()) {
    return NextResponse.json({ error: "goal is required" }, { status: 400 });
  }

  const config = getTeamsConfig();
  if (!config.teams.length) {
    return NextResponse.json({ error: "no teams configured" }, { status: 400 });
  }

  // Step 1: Route goal to teams
  const teamIds = body.team_ids ?? (await routeGoal(body.goal, config.teams)).team_ids;
  const routing = { team_ids: teamIds, reasoning: "manual selection" };

  if (!body.team_ids) {
    const routeResult = await routeGoal(body.goal, config.teams);
    routing.team_ids = routeResult.team_ids;
    routing.reasoning = routeResult.reasoning;
  }

  // Step 2: Run debates and collect specs from each team
  const teamSpecs = await collectTeamSpecs(body.goal, routing.team_ids);

  // Step 3: Merge specs using top judge
  const masterPlan = await mergeSpecs(body.goal, teamSpecs);

  return NextResponse.json({
    ok: true,
    routing,
    team_specs: teamSpecs,
    master_plan: masterPlan,
  });
}

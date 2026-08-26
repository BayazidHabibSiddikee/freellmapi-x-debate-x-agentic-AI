import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import { getTeamsConfig, getTeam, getTeamMembers, getCharacter, getSettings, type Team, type DailyCycle } from "@/lib/business";
import { writeFile, mkdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { execSync } from "node:child_process";

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

/** Check if team is included in a project. */
function isTeamIncludedInProject(teamId: string, project: { included_teams?: string | string[] }): boolean {
  if (!project.included_teams) return true; // default: included
  if (project.included_teams === "all") return true;
  if (Array.isArray(project.included_teams)) {
    return project.included_teams.includes(teamId);
  }
  return false;
}

/** Run the daily autonomous debate loop for a team. */
async function runDailyCycle(team: Team, projectId?: string): Promise<{
  team_id: string;
  leader_summary: string;
  flagged_items: string[];
  transcript: string;
  branch?: string;
  review_status?: string;
}> {
  const settings = getSettings();
  const dailyCycle = team.daily_cycle;
  if (!dailyCycle?.enabled) {
    return { team_id: team.id, leader_summary: "Daily cycle disabled", flagged_items: [], transcript: "" };
  }

  const leaderId = team.roles.lead?.[0];
  const leader = getCharacter(leaderId ?? "");
  const engineerIds = team.roles.engineer ?? [];
  const researcherIds = team.roles.researcher ?? [];

  const members = getTeamMembers(team);
  const memberNames = members.map(id => getCharacter(id)?.name ?? id).join(", ");

  const turns: string[] = [];
  const FLAGGED_KEYWORDS = ["cross-team", "cross team", "another team", "high-impact", "high impact", "escalate", "conflict"];

  // Run iterative debate
  for (let i = 0; i < dailyCycle.iterations; i++) {
    const isLastTurn = i === dailyCycle.iterations - 1;
    const isEngineerTurn = i % 3 === 0 && !isLastTurn;
    const isResearcherTurn = i % 3 === 1 && !isLastTurn;

    let systemPrompt = "";
    let charName = "";
    let role = "";

    if (isLastTurn) {
      // Leader as judge - final distillation
      systemPrompt = `You are ${leader?.name ?? "Team Lead"}, the leader and judge of the "${team.name}" team.
Your teammates: ${memberNames}.

You've watched the team debate. Now distill the key decisions, action items, and any flagged concerns.
Be concise. Flag anything that:
- Touches another team's workspace or files
- Has high impact or risk
- Requires leadership review

Format your response as:
SUMMARY: [2-3 sentence summary]
ACTION_ITEMS: [bullet list]
FLAGGED: [any concerns, or "none"]`;
      charName = leader?.name ?? "Team Lead";
      role = "lead/judge";
    } else if (isEngineerTurn) {
      const engIdx = Math.floor(i / 3) % engineerIds.length;
      const engChar = getCharacter(engineerIds[engIdx] ?? "");
      systemPrompt = `You are ${engChar?.name ?? "Engineer"}, an engineer on the "${team.name}" team.
Your teammates: ${memberNames}.
Propose a concrete implementation approach. Be specific about files and changes.`;
      charName = engChar?.name ?? "Engineer";
      role = "engineer";
    } else if (isResearcherTurn) {
      const resChar = getCharacter(researcherIds[0] ?? "");
      systemPrompt = `You are ${resChar?.name ?? "Researcher"}, the researcher on the "${team.name}" team.
Your teammates: ${memberNames}.
Provide research context, prior art, or data to inform the team's approach.`;
      charName = resChar?.name ?? "Researcher";
      role = "researcher";
    } else {
      // PM or general turn
      const pmId = team.roles.pm?.[0];
      const pmChar = getCharacter(pmId ?? "");
      systemPrompt = `You are ${pmChar?.name ?? "PM"}, the project manager on the "${team.name}" team.
Your teammates: ${memberNames}.
Review the discussion so far and ensure we're addressing requirements and priorities.`;
      charName = pmChar?.name ?? "PM";
      role = "pm";
    }

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
          { role: "user", content: `Daily cycle turn ${i + 1}/${dailyCycle.iterations} for team ${team.name}` },
        ],
        temperature: 0.6,
        max_tokens: 300,
      }),
      signal: AbortSignal.timeout(30_000),
    });

    let text = `${charName} (${role}): [awaiting response]`;
    if (res.ok) {
      const data = await res.json() as { choices?: Array<{ message?: { content?: string } }> };
      text = data.choices?.[0]?.message?.content?.trim() ?? text;
    }

    turns.push(`**${charName} (${role})**: ${text}`);
  }

  // Parse leader's final summary for flagged items
  const lastTurn = turns[turns.length - 1];
  const flaggedItems: string[] = [];
  const summaryMatch = lastTurn.match(/SUMMARY:\s*(.+?)(?=ACTION_ITEMS:|$)/s);
  const flaggedMatch = lastTurn.match(/FLAGGED:\s*(.+?)$/s);

  const leaderSummary = summaryMatch?.[1]?.trim() ?? lastTurn;
  if (flaggedMatch?.[1]?.trim() && flaggedMatch[1].trim().toLowerCase() !== "none") {
    flaggedItems.push(flaggedMatch[1].trim());
  }

  // Check for escalation keywords
  const allText = turns.join("\n").toLowerCase();
  for (const keyword of FLAGGED_KEYWORDS) {
    if (allText.includes(keyword) && !flaggedItems.some(f => f.toLowerCase().includes(keyword))) {
      flaggedItems.push(`Contains keyword: ${keyword}`);
    }
  }

  // Write transcript
  const transcriptDir = team.transcript_dir ?? `~/swordoffice/transcripts/${team.id}`;
  const expandedDir = transcriptDir.replace("~", process.env.HOME ?? "/root");
  await mkdir(expandedDir, { recursive: true });

  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filename = `daily-${timestamp}.md`;
  const filepath = join(expandedDir, filename);

  const content = `# ${team.name} Daily Cycle

**Date**: ${new Date().toISOString()}
**Iterations**: ${dailyCycle.iterations}

---

${turns.join("\n\n")}

---

*Generated by SwordOffice Daily Autonomous Loop*
`;
  await writeFile(filepath, content, "utf-8");

  // If auto_commit is enabled and no escalation, create branch and commit
  let branch: string | undefined;
  let reviewStatus: string | undefined;

  if (dailyCycle.auto_commit && flaggedItems.length === 0 && team.workspace) {
    const expandedWorkspace = team.workspace.replace("~", process.env.HOME ?? "/root");
    const dateStr = new Date().toISOString().split("T")[0];
    branch = dailyCycle.branch_strategy.replace("{date}", dateStr);

    try {
      // Create and switch to feature branch
      execSync(`git checkout -b ${branch}`, { cwd: expandedWorkspace, timeout: 10_000 });

      // Stage changes
      execSync("git add .", { cwd: expandedWorkspace, timeout: 10_000 });

      // Commit
      execSync(`git commit -m "feat(${team.id}): daily cycle ${dateStr}"`, { cwd: expandedWorkspace, timeout: 10_000 });

      // If review panel is required, mark as pending
      if (dailyCycle.requires_review_panel) {
        reviewStatus = "pending_review";
      } else {
        reviewStatus = "approved";
      }
    } catch {
      // If git fails, skip commit
      branch = undefined;
      reviewStatus = undefined;
    }
  }

  return {
    team_id: team.id,
    leader_summary: leaderSummary,
    flagged_items: flaggedItems,
    transcript: filepath,
    branch,
    review_status: reviewStatus,
  };
}

/** Run the leadership round table for escalated items. */
async function runRoundTable(escalatedItems: Array<{ team_id: string; summary: string; flagged: string[] }>): Promise<string> {
  const config = getTeamsConfig();
  const leaders = config.teams.map(t => {
    const leaderId = t.roles.lead?.[0];
    const leader = getCharacter(leaderId ?? "");
    return { team: t.name, leader: leader?.name ?? "Unknown" };
  });

  const rosterText = leaders.map(l => `- ${l.leader} (${l.team})`).join("\n");
  const itemsText = escalatedItems.map(item => `## ${item.team}\n${item.summary}\nFlagged: ${item.flagged.join(", ")}`).join("\n\n");

  const systemPrompt = `You are the Leadership Round Table — the 7 team leaders plus the user.

Leaders:
${rosterText}

Escalated items from today's daily cycles:
${itemsText}

Discuss these items as a group. Identify:
1. Cross-team conflicts or dependencies
2. Resource contention
3. Priority alignment
4. Recommended actions

Be concise and decisive.`;

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
        { role: "user", content: "Review these escalated items and provide recommendations." },
      ],
      temperature: 0.5,
      max_tokens: 800,
    }),
    signal: AbortSignal.timeout(60_000),
  });

  if (!res.ok) return "Round table unavailable";
  const data = await res.json() as { choices?: Array<{ message?: { content?: string } }> };
  return data.choices?.[0]?.message?.content?.trim() ?? "No recommendations";
}

/** Compose daily digest from team summaries. */
async function composeDailyDigest(
  teamResults: Array<{ team_id: string; leader_summary: string; flagged_items: string[] }>,
  roundTable?: string
): Promise<string> {
  const date = new Date().toISOString().split("T")[0];
  const sections = teamResults.map(r => {
    const team = getTeam(r.team_id);
    const flagSection = r.flagged_items.length > 0 ? `\n⚠️ Flagged: ${r.flagged_items.join("; ")}` : "";
    return `### ${team?.name ?? r.team_id}\n${r.leader_summary}${flagSection}`;
  });

  let digest = `# Daily Digest — ${date}\n\n${sections.join("\n\n")}`;

  if (roundTable) {
    digest += `\n\n---\n\n## Leadership Round Table\n${roundTable}`;
  }

  return digest;
}

export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: { team_id?: string; project_id?: string; run_all?: boolean };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }

  const config = getTeamsConfig();
  if (!config.teams.length) {
    return NextResponse.json({ error: "no teams configured" }, { status: 400 });
  }

  // Determine which teams to run
  let teamsToRun: Team[] = [];

  if (body.run_all) {
    teamsToRun = config.teams.filter(t => t.daily_cycle?.enabled);
  } else if (body.team_id) {
    const team = getTeam(body.team_id);
    if (!team) return NextResponse.json({ error: "team not found" }, { status: 404 });
    if (!team.daily_cycle?.enabled) {
      return NextResponse.json({ error: "daily cycle not enabled for this team" }, { status: 400 });
    }
    teamsToRun = [team];
  } else {
    return NextResponse.json({ error: "team_id or run_all required" }, { status: 400 });
  }

  // Run daily cycles
  const results: Array<{ team_id: string; leader_summary: string; flagged_items: string[]; transcript: string; branch?: string; review_status?: string }> = [];

  for (const team of teamsToRun) {
    const result = await runDailyCycle(team, body.project_id);
    results.push(result);
  }

  // Check for escalated items
  const escalatedItems = results.filter(r => r.flagged_items.length > 0);

  // Run round table if there are escalated items
  let roundTable: string | undefined;
  if (escalatedItems.length > 0) {
    roundTable = await runRoundTable(escalatedItems);
  }

  // Compose daily digest
  const digest = await composeDailyDigest(results, roundTable);

  // Write digest to file
  const digestDir = join(process.env.HOME ?? "/root", "swordoffice", "digests");
  await mkdir(digestDir, { recursive: true });
  const dateStr = new Date().toISOString().split("T")[0];
  const digestPath = join(digestDir, `digest-${dateStr}.md`);
  await writeFile(digestPath, digest, "utf-8");

  return NextResponse.json({
    ok: true,
    teams_run: results.map(r => r.team_id),
    digest,
    digest_path: digestPath,
    escalated_count: escalatedItems.length,
    round_table: roundTable ?? null,
    results,
  });
}

/** GET endpoint to check daily cycle status. */
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
  }));

  return NextResponse.json({ ok: true, teams: teamStatus });
}

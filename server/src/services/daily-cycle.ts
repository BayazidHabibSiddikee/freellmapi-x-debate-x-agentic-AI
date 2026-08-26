/**
 * Daily autonomous cycle — shared module.
 *
 * Runs a multi-turn LLM debate for a team with no user present.
 * The team lead doubles as judge for distillation.
 * Engineers commit to feature branches gated by review panel.
 * Cross-team/high-impact changes escalate to leadership round table.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, appendFileSync } from "node:fs";
import { join } from "node:path";
import { execSync } from "node:child_process";

const LLM_BASE = process.env.FREELLM_API_BASE ?? process.env.OPENAI_API_BASE ?? "http://127.0.0.1:3001/v1";

// ── Types ─────────────────────────────────────────────────────────────────────

export type DailyCycleConfig = {
  enabled: boolean;
  iterations: number;
  schedule: string;
  branch_strategy: string;
  auto_commit: boolean;
  requires_review_panel: boolean;
  escalation_threshold?: {
    max_files?: number;
    max_lines?: number;
  };
};

export type TeamConfig = {
  id: string;
  name: string;
  workspace: string;
  selection_mode: string;
  roles: Record<string, string[]>;
  skills?: string[];
  wiki_page?: string;
  transcript_dir?: string;
  daily_cycle?: DailyCycleConfig;
};

export type TeamsConfig = {
  teams: TeamConfig[];
  orchestrator: { character: string; mode: string; team_selection: string; description?: string };
  top_judge?: { character: string; description?: string };
};

export type DailyCycleResult = {
  team_id: string;
  leader_summary: string;
  action_items: string[];
  flagged_items: string[];
  transcript: string;
  branch?: string;
  review_status?: string;
  iterations_completed: number;
  errors: string[];
};

export type RoundTableResult = {
  date: string;
  escalated_items: Array<{ team_id: string; summary: string; flagged: string[] }>;
  discussion: string;
  recommendations: string;
};

// ── Config ────────────────────────────────────────────────────────────────────

const CONFIG_DIR = join(process.cwd(), "..", "config", "business");
const TEAMS_PATH = join(CONFIG_DIR, "teams.json");
const HOME = process.env.HOME ?? "/root";

function getTeamsConfig(): TeamsConfig {
  if (!existsSync(TEAMS_PATH)) {
    return { teams: [], orchestrator: { character: "general_vector", mode: "fan_out_fan_in", team_selection: "all" } };
  }
  try {
    return JSON.parse(readFileSync(TEAMS_PATH, "utf8"));
  } catch {
    return { teams: [], orchestrator: { character: "general_vector", mode: "fan_out_fan_in", team_selection: "all" } };
  }
}

function getTeam(id: string): TeamConfig | null {
  return getTeamsConfig().teams.find(t => t.id === id) ?? null;
}

function getCharacter(id: string): { id: string; name: string; system_prompt?: string } | null {
  const paths = [
    join(process.cwd(), "..", "services", "debate", "characters.json"),
    join(CONFIG_DIR, "custom_characters.json"),
  ];
  for (const p of paths) {
    if (!existsSync(p)) continue;
    try {
      const chars = JSON.parse(readFileSync(p, "utf8")) as Array<{ id: string; name: string; system_prompt?: string }>;
      const found = chars.find(c => c.id === id);
      if (found) return found;
    } catch { /* skip */ }
  }
  return null;
}

function getTeamMembers(team: TeamConfig): string[] {
  const all = new Set<string>();
  for (const members of Object.values(team.roles)) {
    for (const id of members) all.add(id);
  }
  return [...all];
}

// ── LLM ───────────────────────────────────────────────────────────────────────

function freellmKey(): string {
  if (process.env.FREELLM_API_KEY) return process.env.FREELLM_API_KEY;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Database = require("better-sqlite3");
    const dbPath = join(process.cwd(), "..", "server", "data", "freeapi.db");
    const db = new Database(dbPath, { readonly: true });
    const row = db.prepare("SELECT value FROM settings WHERE key = 'unified_api_key'").get() as { value?: string } | undefined;
    db.close();
    if (row?.value) return row.value;
  } catch { /* fall through */ }
  return "not-needed";
}

async function llmCall(systemPrompt: string, userMessage: string, maxTokens = 300, temperature = 0.6): Promise<string> {
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
        { role: "user", content: userMessage },
      ],
      temperature,
      max_tokens: maxTokens,
    }),
    signal: AbortSignal.timeout(45_000),
  });

  if (!res.ok) throw new Error(`LLM returned ${res.status}`);
  const data = await res.json() as { choices?: Array<{ message?: { content?: string } }> };
  return data.choices?.[0]?.message?.content?.trim() ?? "";
}

// ── Transcript ────────────────────────────────────────────────────────────────

function getTranscriptDir(team: TeamConfig): string {
  const dir = team.transcript_dir ?? `~/swordoffice/transcripts/${team.id}`;
  return dir.replace("~", HOME);
}

function ensureDir(dir: string): void {
  mkdirSync(dir, { recursive: true });
}

function writeTranscriptHeader(team: TeamConfig, filepath: string): void {
  const content = `# ${team.name} Daily Cycle

**Date**: ${new Date().toISOString()}
**Iterations**: ${team.daily_cycle?.iterations ?? 12}

---

`;
  writeFileSync(filepath, content, "utf-8");
}

function appendTurn(filepath: string, turn: string): void {
  appendFileSync(filepath, turn + "\n\n", "utf-8");
}

function writeTranscriptFooter(filepath: string): void {
  appendFileSync(filepath, `\n---\n\n*Generated by SwordOffice Daily Autonomous Loop*\n`, "utf-8");
}

// ── Escalation Detection ──────────────────────────────────────────────────────

const FLAGGED_KEYWORDS = ["cross-team", "cross team", "another team", "high-impact", "high impact", "escalate", "conflict"];

function detectEscalation(turns: string[], config?: DailyCycleConfig): { flagged: boolean; reasons: string[] } {
  const reasons: string[] = [];
  const allText = turns.join("\n").toLowerCase();

  // Keyword-based
  for (const keyword of FLAGGED_KEYWORDS) {
    if (allText.includes(keyword)) {
      reasons.push(`Contains keyword: ${keyword}`);
    }
  }

  // Size-based (if threshold configured)
  if (config?.escalation_threshold) {
    const { max_files = 5, max_lines = 200 } = config.escalation_threshold;

    // Estimate files touched from engineer turns
    const fileMentions = allText.match(/(?:file|change|modify|update|create|delete|add|remove)\s+[\w/._-]+\.\w+/g) ?? [];
    if (fileMentions.length > max_files) {
      reasons.push(`Files touched (${fileMentions.length}) exceeds threshold (${max_files})`);
    }

    // Estimate lines from turn text (rough heuristic)
    const lineEstimates = turns.filter(t => t.includes("engineer")).map(t => {
      const lines = t.split("\n").length;
      return lines;
    });
    const totalLines = lineEstimates.reduce((a, b) => a + b, 0);
    if (totalLines > max_lines) {
      reasons.push(`Estimated lines (${totalLines}) exceeds threshold (${max_lines})`);
    }
  }

  return { flagged: reasons.length > 0, reasons };
}

// ── Parse Leader Summary ──────────────────────────────────────────────────────

function parseLeaderSummary(text: string): { summary: string; actionItems: string[]; flagged: string[] } {
  const summaryMatch = text.match(/SUMMARY:\s*([\s\S]*?)(?=ACTION_ITEMS:|$)/i);
  const actionMatch = text.match(/ACTION_ITEMS:\s*([\s\S]*?)(?=FLAGGED:|$)/i);
  const flaggedMatch = text.match(/FLAGGED:\s*([\s\S]*?)$/i);

  const summary = summaryMatch?.[1]?.trim() ?? text.slice(0, 500);
  const actionItems = actionMatch?.[1]?.trim()
    ?.split("\n")
    .map(l => l.replace(/^[-*]\s*/, "").trim())
    .filter(Boolean) ?? [];
  const flagged = flaggedMatch?.[1]?.trim()
    ?.split("\n")
    .map(l => l.replace(/^[-*]\s*/, "").trim())
    .filter(f => f.toLowerCase() !== "none" && f.length > 0) ?? [];

  return { summary, actionItems, flagged };
}

// ── Review Panel ──────────────────────────────────────────────────────────────

async function runReviewPanel(workspace: string, branch: string): Promise<{ approved: boolean; feedback: string }> {
  const expandedWorkspace = workspace.replace("~", HOME);

  try {
    // Get diff against main
    const diff = execSync(`git diff main...${branch} --stat`, { cwd: expandedWorkspace, timeout: 10_000, encoding: "utf-8" });
    const fullDiff = execSync(`git diff main...${branch}`, { cwd: expandedWorkspace, timeout: 30_000, encoding: "utf-8" });

    if (!fullDiff.trim()) {
      return { approved: true, feedback: "No changes to review" };
    }

    // Reviewer perspective
    const reviewerPrompt = `You are a Code Reviewer. Review this diff and approve or reject it.
Diff stats:
${diff}

Full diff (first 3000 chars):
${fullDiff.slice(0, 3000)}

Respond with:
VERDICT: APPROVED or REJECTED
FEEDBACK: [brief explanation]`;

    const reviewResult = await llmCall(reviewerPrompt, "Review this code change.", 300, 0.3);
    const approved = reviewResult.toUpperCase().includes("APPROVED");
    const feedback = reviewResult.replace(/VERDICT:\s*(APPROVED|REJECTED)\s*/i, "").trim();

    return { approved, feedback };
  } catch (err) {
    return { approved: false, feedback: `Review failed: ${err instanceof Error ? err.message : String(err)}` };
  }
}

// ── Git Operations ────────────────────────────────────────────────────────────

function createBranch(workspace: string, branch: string): boolean {
  const expandedWorkspace = workspace.replace("~", HOME);
  try {
    execSync(`git checkout -b ${branch}`, { cwd: expandedWorkspace, timeout: 10_000 });
    return true;
  } catch {
    return false;
  }
}

function commitChanges(workspace: string, message: string): boolean {
  const expandedWorkspace = workspace.replace("~", HOME);
  try {
    execSync("git add .", { cwd: expandedWorkspace, timeout: 10_000 });
    execSync(`git commit -m "${message}"`, { cwd: expandedWorkspace, timeout: 10_000 });
    return true;
  } catch {
    return false;
  }
}

// ── Main: Run Daily Cycle ─────────────────────────────────────────────────────

export async function runDailyCycle(team: TeamConfig): Promise<DailyCycleResult> {
  const dailyCycle = team.daily_cycle;
  if (!dailyCycle?.enabled) {
    return {
      team_id: team.id,
      leader_summary: "Daily cycle disabled",
      action_items: [],
      flagged_items: [],
      transcript: "",
      iterations_completed: 0,
      errors: [],
    };
  }

  const leaderId = team.roles.lead?.[0];
  const leader = getCharacter(leaderId ?? "");
  const engineerIds = team.roles.engineer ?? [];
  const researcherIds = team.roles.researcher ?? [];
  const pmIds = team.roles.pm ?? [];

  const members = getTeamMembers(team);
  const memberNames = members.map(id => getCharacter(id)?.name ?? id).join(", ");

  const turns: string[] = [];
  const errors: string[] = [];

  // Setup transcript
  const transcriptDir = getTranscriptDir(team);
  ensureDir(transcriptDir);
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filepath = join(transcriptDir, `daily-${timestamp}.md`);
  writeTranscriptHeader(team, filepath);

  // Run iterative debate
  for (let i = 0; i < dailyCycle.iterations; i++) {
    const isLastTurn = i === dailyCycle.iterations - 1;
    const turnIndex = i % 3;

    let systemPrompt = "";
    let charName = "";
    let role = "";

    if (isLastTurn) {
      // Leader as judge — final distillation
      systemPrompt = `You are ${leader?.name ?? "Team Lead"}, the leader and judge of the "${team.name}" team.
Your teammates: ${memberNames}.

You've watched the team debate for ${dailyCycle.iterations} turns. Now distill the key decisions, action items, and any flagged concerns.

Be concise. Flag anything that:
- Touches another team's workspace or files
- Has high impact or risk
- Requires leadership review

Format your response as:
SUMMARY: [2-3 sentence summary]
ACTION_ITEMS: [bullet list, one per line]
FLAGGED: [any concerns, or "none"]`;
      charName = leader?.name ?? "Team Lead";
      role = "lead/judge";
    } else if (turnIndex === 0) {
      // Engineer turn
      const engIdx = Math.floor(i / 3) % engineerIds.length;
      const engChar = getCharacter(engineerIds[engIdx] ?? "");
      systemPrompt = `You are ${engChar?.name ?? "Engineer"}, an engineer on the "${team.name}" team.
Your teammates: ${memberNames}.
Propose a concrete implementation approach. Be specific about files and changes.
Keep response under 200 words.`;
      charName = engChar?.name ?? "Engineer";
      role = "engineer";
    } else if (turnIndex === 1) {
      // Researcher turn
      const resChar = getCharacter(researcherIds[0] ?? "");
      systemPrompt = `You are ${resChar?.name ?? "Researcher"}, the researcher on the "${team.name}" team.
Your teammates: ${memberNames}.
Provide research context, prior art, or data to inform the team's approach.
Keep response under 200 words.`;
      charName = resChar?.name ?? "Researcher";
      role = "researcher";
    } else {
      // PM turn
      const pmChar = getCharacter(pmIds[0] ?? "");
      systemPrompt = `You are ${pmChar?.name ?? "PM"}, the project manager on the "${team.name}" team.
Your teammates: ${memberNames}.
Review the discussion so far and ensure we're addressing requirements and priorities.
Keep response under 200 words.`;
      charName = pmChar?.name ?? "PM";
      role = "pm";
    }

    const userMsg = `Daily cycle turn ${i + 1}/${dailyCycle.iterations} for team ${team.name}`;

    try {
      const text = await llmCall(systemPrompt, userMsg, isLastTurn ? 600 : 250, 0.6);
      const turnText = `**${charName} (${role})**: ${text || "[no response]"}`;
      turns.push(turnText);
      appendTurn(filepath, turnText);
    } catch (err) {
      const errorMsg = `[iteration ${i + 1} failed: ${err instanceof Error ? err.message : String(err)}]`;
      const turnText = `**${charName} (${role})**: ${errorMsg}`;
      turns.push(turnText);
      appendTurn(filepath, turnText);
      errors.push(errorMsg);
    }
  }

  writeTranscriptFooter(filepath);

  // Parse leader's final summary
  const lastTurn = turns[turns.length - 1] ?? "";
  const { summary, actionItems, flagged: parsedFlagged } = parseLeaderSummary(lastTurn);

  // Detect escalation (keyword + size-based)
  const { flagged: sizeFlagged, reasons: sizeReasons } = detectEscalation(turns, dailyCycle);
  const allFlagged = [...new Set([...parsedFlagged, ...sizeReasons])];

  // Git operations (if auto_commit enabled and no flags)
  let branch: string | undefined;
  let reviewStatus: string | undefined;

  if (dailyCycle.auto_commit && allFlagged.length === 0 && team.workspace) {
    const dateStr = new Date().toISOString().split("T")[0];
    branch = dailyCycle.branch_strategy.replace("{date}", dateStr);

    if (createBranch(team.workspace, branch)) {
      if (commitChanges(team.workspace, `feat(${team.id}): daily cycle ${dateStr}`)) {
        if (dailyCycle.requires_review_panel) {
          const review = await runReviewPanel(team.workspace, branch);
          reviewStatus = review.approved ? "approved" : "rejected";
          if (!review.approved) {
            allFlagged.push(`Review rejected: ${review.feedback}`);
          }
        } else {
          reviewStatus = "approved";
        }
      } else {
        allFlagged.push("Commit failed — no changes to commit");
        branch = undefined;
      }
    } else {
      allFlagged.push("Branch creation failed");
      branch = undefined;
    }
  }

  return {
    team_id: team.id,
    leader_summary: summary,
    action_items: actionItems,
    flagged_items: allFlagged,
    transcript: filepath,
    branch,
    review_status: reviewStatus,
    iterations_completed: dailyCycle.iterations,
    errors,
  };
}

// ── Leadership Round Table ────────────────────────────────────────────────────

export async function runRoundTable(escalatedItems: Array<{ team_id: string; summary: string; flagged: string[] }>): Promise<RoundTableResult> {
  const config = getTeamsConfig();
  const leaders = config.teams.map(t => {
    const leaderId = t.roles.lead?.[0];
    const leader = getCharacter(leaderId ?? "");
    return { team: t.name, leader: leader?.name ?? "Unknown" };
  });

  const rosterText = leaders.map(l => `- ${l.leader} (${l.team})`).join("\n");
  const itemsText = escalatedItems.map(item => {
    const team = getTeam(item.team_id);
    return `## ${team?.name ?? item.team_id}\n${item.summary}\nFlagged: ${item.flagged.join(", ")}`;
  }).join("\n\n");

  const systemPrompt = `You are the Leadership Round Table — the 7 team leaders.

Leaders:
${rosterText}

Escalated items from today's daily cycles:
${itemsText}

Discuss these items as a group. Identify:
1. Cross-team conflicts or dependencies
2. Resource contention
3. Priority alignment
4. Recommended actions

Be concise and decisive. Format as:
DISCUSSION: [analysis]
RECOMMENDATIONS: [numbered list]`;

  let discussion = "Round table unavailable";
  let recommendations = "No recommendations";

  try {
    const result = await llmCall(systemPrompt, "Review these escalated items.", 800, 0.5);
    const discMatch = result.match(/DISCUSSION:\s*([\s\S]*?)(?=RECOMMENDATIONS:|$)/i);
    const recMatch = result.match(/RECOMMENDATIONS:\s*([\s\S]*?)$/i);
    discussion = discMatch?.[1]?.trim() ?? result;
    recommendations = recMatch?.[1]?.trim() ?? "No recommendations";
  } catch (err) {
    discussion = `Round table failed: ${err instanceof Error ? err.message : String(err)}`;
  }

  // Persist round table
  const roundTableDir = join(HOME, "swordoffice", "round-tables");
  ensureDir(roundTableDir);
  const dateStr = new Date().toISOString().split("T")[0];
  const filepath = join(roundTableDir, `round-table-${dateStr}.md`);

  const content = `# Leadership Round Table — ${dateStr}

## Escalated Items
${escalatedItems.map(item => `- **${item.team_id}**: ${item.flagged.join("; ")}`).join("\n")}

## Discussion
${discussion}

## Recommendations
${recommendations}

---
*Generated by SwordOffice Leadership Round Table*
`;
  writeFileSync(filepath, content, "utf-8");

  return { date: dateStr, escalated_items: escalatedItems, discussion, recommendations };
}

// ── Daily Digest ──────────────────────────────────────────────────────────────

export async function composeDailyDigest(
  teamResults: DailyCycleResult[],
  roundTable?: RoundTableResult
): Promise<string> {
  const date = new Date().toISOString().split("T")[0];
  const sections = teamResults.map(r => {
    const team = getTeam(r.team_id);
    const flagSection = r.flagged_items.length > 0 ? `\n⚠️ Flagged: ${r.flagged_items.join("; ")}` : "";
    const errorSection = r.errors.length > 0 ? `\n❌ Errors: ${r.errors.join("; ")}` : "";
    return `### ${team?.name ?? r.team_id}\n${r.leader_summary}${flagSection}${errorSection}`;
  });

  let digest = `# Daily Digest — ${date}\n\n${sections.join("\n\n")}`;

  if (roundTable) {
    digest += `\n\n---\n\n## Leadership Round Table\n${roundTable.discussion}\n\n### Recommendations\n${roundTable.recommendations}`;
  }

  // Persist digest
  const digestDir = join(HOME, "swordoffice", "digests");
  ensureDir(digestDir);
  const digestPath = join(digestDir, `digest-${date}.md`);
  writeFileSync(digestPath, digest, "utf-8");

  return digest;
}

// ── Run All Teams ─────────────────────────────────────────────────────────────

export async function runAllTeamsDailyCycle(): Promise<{
  results: DailyCycleResult[];
  digest: string;
  round_table?: RoundTableResult;
}> {
  const config = getTeamsConfig();
  const enabledTeams = config.teams.filter(t => t.daily_cycle?.enabled);

  const results: DailyCycleResult[] = [];
  for (const team of enabledTeams) {
    console.log(`[daily-cycle] Running for team: ${team.name}`);
    const result = await runDailyCycle(team);
    results.push(result);
    console.log(`[daily-cycle] Completed: ${team.name} (${result.iterations_completed} iterations, ${result.errors.length} errors)`);
  }

  // Check for escalated items
  const escalatedItems = results
    .filter(r => r.flagged_items.length > 0)
    .map(r => ({ team_id: r.team_id, summary: r.leader_summary, flagged: r.flagged_items }));

  // Run round table if needed
  let roundTable: RoundTableResult | undefined;
  if (escalatedItems.length > 0) {
    console.log(`[daily-cycle] Running round table for ${escalatedItems.length} escalated items`);
    roundTable = await runRoundTable(escalatedItems);
  }

  const digest = await composeDailyDigest(results, roundTable);

  return { results, digest, round_table: roundTable };
}

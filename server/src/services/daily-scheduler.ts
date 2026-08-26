/**
 * Daily cycle scheduler — reads teams.json and registers cron jobs.
 *
 * Each team with daily_cycle.enabled gets a cron job at daily_cycle.schedule.
 * On trigger, runs the full daily cycle (debate → lead distillation → commit → review → round table).
 */

import cron from "node-cron";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { runDailyCycle, runRoundTable, composeDailyDigest } from "./daily-cycle.js";
import type { TeamConfig, TeamsConfig, DailyCycleResult, RoundTableResult } from "./daily-cycle.js";

const CONFIG_DIR = join(process.cwd(), "..", "config", "business");
const TEAMS_PATH = join(CONFIG_DIR, "teams.json");

// ── State ─────────────────────────────────────────────────────────────────────

const scheduledJobs = new Map<string, ReturnType<typeof cron.schedule>>();
let isRunning = false;

// ── Config ────────────────────────────────────────────────────────────────────

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

// ── Scheduler ─────────────────────────────────────────────────────────────────

function registerTeamJob(team: TeamConfig): void {
  if (!team.daily_cycle?.enabled) return;
  if (!cron.validate(team.daily_cycle.schedule)) {
    console.error(`[scheduler] Invalid cron schedule for team ${team.id}: ${team.daily_cycle.schedule}`);
    return;
  }

  // Stop existing job if any
  const existing = scheduledJobs.get(team.id);
  if (existing) {
    existing.stop();
  }

  const job = cron.schedule(team.daily_cycle.schedule, async () => {
    if (isRunning) {
      console.log(`[scheduler] Daily cycle already running, skipping ${team.id}`);
      return;
    }

    isRunning = true;
    console.log(`[scheduler] Triggering daily cycle for team: ${team.name} (${team.id})`);

    try {
      const result = await runDailyCycle(team);
      console.log(`[scheduler] Completed: ${team.id} — ${result.iterations_completed} iterations, ${result.flagged_items.length} flagged`);

      // Check if round table needed
      if (result.flagged_items.length > 0) {
        console.log(`[scheduler] Escalating to round table for team: ${team.id}`);
        await runRoundTable([{
          team_id: result.team_id,
          summary: result.leader_summary,
          flagged: result.flagged_items,
        }]);
      }
    } catch (err) {
      console.error(`[scheduler] Error running daily cycle for ${team.id}:`, err);
    } finally {
      isRunning = false;
    }
  });

  scheduledJobs.set(team.id, job);
  console.log(`[scheduler] Registered job for team ${team.id} at ${team.daily_cycle.schedule}`);
}

function unregisterTeamJob(teamId: string): void {
  const job = scheduledJobs.get(teamId);
  if (job) {
    job.stop();
    scheduledJobs.delete(teamId);
    console.log(`[scheduler] Unregistered job for team ${teamId}`);
  }
}

// ── Public API ────────────────────────────────────────────────────────────────

/** Register all enabled teams from teams.json. */
export function startScheduler(): void {
  console.log("[scheduler] Starting daily cycle scheduler...");
  const config = getTeamsConfig();

  for (const team of config.teams) {
    registerTeamJob(team);
  }

  console.log(`[scheduler] Registered ${scheduledJobs.size} team jobs`);
}

/** Stop all scheduled jobs. */
export function stopScheduler(): void {
  for (const [teamId, job] of scheduledJobs) {
    job.stop();
  }
  scheduledJobs.clear();
  console.log("[scheduler] Stopped all jobs");
}

/** Re-read teams.json and re-register all jobs. */
export function reloadScheduler(): void {
  console.log("[scheduler] Reloading config...");
  stopScheduler();
  startScheduler();
}

/** Get status of all scheduled jobs. */
export function getSchedulerStatus(): Array<{ team_id: string; schedule: string; enabled: boolean; registered: boolean }> {
  const config = getTeamsConfig();
  return config.teams.map(t => ({
    team_id: t.id,
    schedule: t.daily_cycle?.schedule ?? "N/A",
    enabled: t.daily_cycle?.enabled ?? false,
    registered: scheduledJobs.has(t.id),
  }));
}

/** Manually trigger a daily cycle for a specific team. */
export async function triggerTeamCycle(teamId: string): Promise<DailyCycleResult | null> {
  const config = getTeamsConfig();
  const team = config.teams.find(t => t.id === teamId);
  if (!team) {
    console.error(`[scheduler] Team not found: ${teamId}`);
    return null;
  }

  console.log(`[scheduler] Manual trigger for team: ${team.name}`);
  return runDailyCycle(team);
}

/** Manually trigger daily cycles for all enabled teams. */
export async function triggerAllTeams(): Promise<{
  results: DailyCycleResult[];
  digest: string;
  round_table?: RoundTableResult;
}> {
  console.log("[scheduler] Manual trigger for all teams");
  const config = getTeamsConfig();
  const enabledTeams = config.teams.filter(t => t.daily_cycle?.enabled);

  const results: DailyCycleResult[] = [];
  for (const team of enabledTeams) {
    const result = await runDailyCycle(team);
    results.push(result);
  }

  const escalatedItems = results
    .filter(r => r.flagged_items.length > 0)
    .map(r => ({ team_id: r.team_id, summary: r.leader_summary, flagged: r.flagged_items }));

  let roundTable: RoundTableResult | undefined;
  if (escalatedItems.length > 0) {
    roundTable = await runRoundTable(escalatedItems);
  }

  const digest = await composeDailyDigest(results, roundTable);

  return { results, digest, round_table: roundTable };
}

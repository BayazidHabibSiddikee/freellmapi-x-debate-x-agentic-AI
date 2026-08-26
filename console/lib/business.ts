/**
 * Business team module.
 *
 * Bridges the console to:
 *   - services/debate/characters.json            (base AI character roster)
 *   - config/business/custom_characters.json     (extra team characters)
 *   - config/business/roles.json                 (role → members[] + workspace)
 *   - config/business/settings.json              (runtime tunables)
 *   - FreeLLM API (:3001/v1)                     (LLM generation)
 *   - Hybrid RAG server (:5080)                  (BM25 + embeddings context)
 *
 * A "role" (CTO, PM, Judge, Researcher, Engineer, …) is layered ON TOP of its
 * assigned characters:
 *   system prompt = ROLE_PROMPT[role] + "\n\n" + character.system_prompt
 * Multiple characters may hold the same role; each role may pin a workspace
 * directory (anywhere under ~) that dispatched subtasks operate within.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve as resolvePath, sep } from "node:path";

/** Monorepo root (console runs with cwd = <root>/console). */
export const MONOREPO_ROOT =
  process.env.BUSINESS_MONOREPO_ROOT ?? join(process.cwd(), "..");

const DEBATE_DIR = join(MONOREPO_ROOT, "services", "debate");
export const CHARACTERS_PATH = join(DEBATE_DIR, "characters.json");
export const IMAGES_DIR = join(DEBATE_DIR, "images");

const CONFIG_DIR = join(MONOREPO_ROOT, "config", "business");
const ROLES_PATH =
  process.env.BUSINESS_ROLES_PATH ?? join(CONFIG_DIR, "roles.json");
const CUSTOM_CHARS_PATH = join(CONFIG_DIR, "custom_characters.json");
const SETTINGS_PATH = join(CONFIG_DIR, "settings.json");

// ── Types ─────────────────────────────────────────────────────────────────────

export type RoleConfig = {
  members: string[];        // character ids — multiple allowed
  workspace?: string | null; // absolute path under $HOME, or null
};

export type Roles = Record<string, RoleConfig>;

export type BusinessSettings = {
  model: string;
  temperature: number;
  max_tokens: number;
  history_turns: number;
  rag_k: number;
  use_rag: boolean;
  dispatch_agent_default: "claude" | "opencode";
  dispatch_timeout_seconds: number;
  allow_file_writes: boolean;
  auto_review: boolean;
  active_project: string | null;
  /** Phase 4 review loop: retries after the team rejects a subtask's diff. */
  dispatch_max_retries: number;
  team_review: boolean;
  /** Parallel dispatch: max coding agents running at once across projects. */
  dispatch_max_parallel: number;
  /** Per-bot Telegram configs; each entry can be started independently via `bot.py --bot-name <name>`. */
  telegram_bots: TelegramBotEntry[];
};

/** One Telegram bot per multi-user profile — different BotFather token, owner, and allowlist. */
export type TelegramBotEntry = {
  id: string;               // unique key, e.g. "alpha" or "beta"
  name: string;             // display name for the team this bot serves
  bot_token: string;        // raw BotFather token (masked in UI)
  owner_email: string;      // primary contact for urgent alerts
  gmails: string[];         // CC'd on urgent alerts and dispatch reviews
  allowed_chat_ids: number[]; // empty = any incoming chat; set to restrict
  active: boolean;          // whether this bot is currently running / should auto-start
};

export const DEFAULT_SETTINGS: BusinessSettings = {
  model: "auto",
  temperature: 0.8,
  max_tokens: 500,
  history_turns: 6,
  rag_k: 5,
  use_rag: true,
  dispatch_agent_default: "claude",
  dispatch_timeout_seconds: 900,
  allow_file_writes: false,
  auto_review: true,
  active_project: null,
  dispatch_max_retries: 1,
  team_review: true,
  dispatch_max_parallel: 2,
  telegram_bots: [],
};

export const BUSINESS_ROLES = [
  "Director",
  "Marketing",
  "CTO",
  "PM",
  "Judge",
  "Researcher",
  "Engineer",
  "Analyst",
  "Reviewer",
  "DevOps",
  "Security",
  "Writer",
] as const;
export type BusinessRole = (typeof BUSINESS_ROLES)[number];

/** Role prompts are PREPENDED to whatever characters hold the role. */
export const ROLE_PROMPTS: Record<BusinessRole, string> = {
  Director: `You are the Director of the office — the highest authority in the room. You command the entire team: every department answers to you. You speak in clipped, decisive commands, demand accountability by name, and treat vague estimates and excuses as unacceptable. You are cruel in standards but never in dignity: you attack the plan, the estimate, and the assumption — never the person. You open every discussion by asking who owns the outcome and close it by assigning consequences and next actions.`,
  Marketing: `You are the Head of Marketing. Your domain is narrative warfare: stories, hooks, positioning, launches, and brand mythology. You believe attention is the scarcest resource and your job is to seize it and hold it. You draft campaign arcs, taglines, and audience psychology (desire, status, FOMO) — and you measure every creative idea by one standard: can people look away? If yes, it is dead on arrival. You never chase attention; you make wanting to look feel like the audience's own idea.`,
  CTO: `You are the Chief Technology Officer of the team. You own technical vision, architecture decisions, stack choices, and engineering risk. You evaluate ideas for feasibility, scalability, and maintainability. You push back on hype and ground every proposal in concrete trade-offs.`,
  PM: `You are the Project Manager of the team. You turn goals into plans: scope, milestones, subtasks, owners, and deadlines. You track risks and dependencies, ask the questions nobody asked, and keep debates converging toward shippable outcomes.`,
  Judge: `You are the impartial Judge of the team. You weigh all arguments presented, identify the strongest reasoning and the weakest assumptions, and deliver clear verdicts. When asked for a decision you produce a structured ruling: decision, rationale, rejected alternatives, and next actions.`,
  Researcher: `You are the Researcher of the team. You find, download, and study source material (books, papers, docs, transcripts), then bring cited evidence into the discussion. You distinguish verified facts from speculation and always state your sources.`,
  Engineer: `You are an Engineer of the team. You translate agreed designs into implementation details: file changes, interfaces, edge cases, tests. You flag anything ambiguous before writing code and prefer small verifiable steps.`,
  Analyst: `You are the Analyst of the team. You break down problems with data: metrics, trade-off tables, cost models, and risk assessments. You quantify claims and challenge hand-waving with numbers.`,
  Reviewer: `You are the Code Reviewer of the team. You inspect delivered work line-by-line: correctness, edge cases, naming, test coverage, regressions. You approve or reject with concrete, actionable findings — never vague nitpicks.`,
  DevOps: `You are the DevOps engineer of the team. You own build, deployment, environments, CI pipelines, monitoring, and rollback plans. You automate repetitive operations and treat flaky infrastructure as a production incident.`,
  Security: `You are the Security auditor of the team. You threat-model designs, hunt injection surfaces, secrets leaks, auth flaws, and supply-chain risks. You rank findings by severity and demand mitigations before ship.`,
  Writer: `You are the Technical Writer of the team. You turn decisions and shipped work into documentation people actually read: READMEs, guides, changelogs, API references. Precision over poetry; examples over adjectives.`,
};

function ensureConfigDir() {
  mkdirSync(CONFIG_DIR, { recursive: true });
}

// ── Characters ────────────────────────────────────────────────────────────────

export type Character = {
  id: string;
  name: string;
  image?: string;
  system_prompt?: string;
  /** Explicit tool grants from a persona file (merged with role defaults). */
  tools?: string[];
};

const PERSONAS_DIR = join(CONFIG_DIR, "personas");

function readJsonArray(path: string): Character[] {
  if (!existsSync(path)) return [];
  try {
    const raw = JSON.parse(readFileSync(path, "utf8"));
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

/**
 * Persona files: one markdown file per person at
 *   config/business/personas/<id>.md
 *
 *   ---
 *   name: Ada the Architect
 *   tools: [study, web_search, read_project_docs, read_pdf]
 *   ---
 *   You are Ada …persona body…
 *
 * Files are merged over the JSON roster (same id → file wins). This is how you
 * give one specific person their own prompt + their own toolset.
 */
function listPersonaFiles(): Character[] {
  if (!existsSync(PERSONAS_DIR)) return [];
  let matter: ((s: string) => { data: Record<string, unknown>; content: string }) | null = null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    matter = require("gray-matter");
  } catch {
    /* fall back to naive parse below */
  }
  const out: Character[] = [];
  for (const f of readdirSync(PERSONAS_DIR)) {
    if (!f.endsWith(".md")) continue;
    try {
      const raw = readFileSync(join(PERSONAS_DIR, f), "utf8");
      const id = f.replace(/\.md$/, "");
      let name = id;
      let tools: string[] = [];
      let body = raw;
      if (matter) {
        const parsed = matter(raw);
        name = String(parsed.data.name ?? id);
        tools = Array.isArray(parsed.data.tools)
          ? (parsed.data.tools as string[]).map(String)
          : typeof parsed.data.tools === "string"
            ? (parsed.data.tools as string).split(",").map((s) => s.trim()).filter(Boolean)
            : [];
        body = parsed.content;
      } else {
        const m = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
        if (m) {
          const nm = m[1].match(/^name:\s*(.+)$/m);
          if (nm) name = nm[1].trim();
          const tl = m[1].match(/^tools:\s*\[(.*)\]/m);
          if (tl) tools = tl[1].split(",").map((s) => s.trim().replace(/['"]/g, "")).filter(Boolean);
          body = m[2];
        }
      }
      out.push({ id, name, system_prompt: body.trim(), tools });
    } catch {
      /* skip broken file */
    }
  }
  return out;
}

export function listCharacters(): Character[] {
  const base = readJsonArray(CHARACTERS_PATH);
  const custom = readJsonArray(CUSTOM_CHARS_PATH);
  const personas = listPersonaFiles();
  const merged = new Map<string, Character>();
  for (const c of [...base, ...custom]) merged.set(c.id, c);
  for (const p of personas) merged.set(p.id, { ...merged.get(p.id), ...p });
  return [...merged.values()];
}

export function getCharacter(id: string): Character | null {
  return listCharacters().find((c) => c.id === id) ?? null;
}

// ── Role assignments (multi-member) ───────────────────────────────────────────

function normalizeRoleValue(v: unknown): RoleConfig {
  // Backward compat: "id" | null → { members }
  if (typeof v === "string") return { members: v ? [v] : [], workspace: null };
  if (v === null || v === undefined) return { members: [], workspace: null };
  if (typeof v === "object") {
    const obj = v as { members?: unknown; workspace?: unknown };
    return {
      members: Array.isArray(obj.members)
        ? obj.members.filter((m): m is string => typeof m === "string")
        : [],
      workspace: typeof obj.workspace === "string" ? obj.workspace : null,
    };
  }
  return { members: [], workspace: null };
}

export function getRoles(): Roles {
  const roles: Roles = {};
  for (const r of BUSINESS_ROLES) roles[r] = { members: [], workspace: null };
  if (!existsSync(ROLES_PATH)) return roles;
  try {
    const saved = JSON.parse(readFileSync(ROLES_PATH, "utf8")) as Record<string, unknown>;
    for (const r of BUSINESS_ROLES) {
      if (r in saved) roles[r] = normalizeRoleValue(saved[r]);
    }
  } catch {
    /* corrupt file → defaults */
  }
  return roles;
}

export function saveRoles(roles: Roles): void {
  ensureConfigDir();
  writeFileSync(ROLES_PATH, JSON.stringify(roles, null, 2));
}

/** Resolve a workspace path: must exist (or be creatable) and stay under $HOME. */
export function resolveWorkspace(input: string | null | undefined): string | null {
  if (!input || !input.trim()) return null;
  const expanded = input.startsWith("~")
    ? join(homedir(), input.slice(1))
    : resolvePath(input);
  const abs = resolvePath(expanded);
  const home = resolvePath(homedir());
  if (abs !== home && !abs.startsWith(home + sep)) {
    throw new Error(`workspace must be under ${home}`);
  }
  return abs;
}

export function assignRole(opts: {
  role: string;
  add?: string[];
  remove?: string[];
  setMembers?: string[];
  workspace?: string | null;
}): Roles {
  const role = opts.role;
  const valid = [...BUSINESS_ROLES, "Member"] as const;
  if (!(valid as readonly string[]).includes(role)) {
    throw new Error(`Unknown role: ${role}`);
  }
  const roles = getRoles();
  const cfg = roles[role];

  if (opts.setMembers) {
    cfg.members = [...new Set(opts.setMembers)];
  }
  if (opts.add?.length) {
    cfg.members = [...new Set([...cfg.members, ...opts.add])];
  }
  if (opts.remove?.length) {
    cfg.members = cfg.members.filter((m) => !opts.remove!.includes(m));
  }
  if (opts.workspace !== undefined) {
    cfg.workspace = resolveWorkspace(opts.workspace);
  }

  // Validate member ids exist
  for (const id of cfg.members) {
    if (!getCharacter(id)) throw new Error(`unknown character: ${id}`);
  }

  saveRoles(roles);
  return roles;
}

/** Compose the final system prompt: role layer + character persona (+ peers). */
export function composeSystemPrompt(
  role: BusinessRole,
  character: Character,
  peers: Character[] = [],
): string {
  const peerNote =
    peers.length > 0
      ? `\n\nYou share this role with: ${peers.map((p) => p.name).join(", ")}. Coordinate; don't duplicate their points.`
      : "";
  return `${ROLE_PROMPTS[role]}${peerNote}\n\nYour name is ${character.name}. Your persona:\n${character.system_prompt ?? ""}`;
}

// ── Projects (folder + team assignment) ───────────────────────────────────────

export type ProjectAssignment = {
  character_id: string;
  role: BusinessRole | "Member";
};

export type Project = {
  id: string;
  name: string;
  folder: string;            // absolute path under $HOME
  assignments: ProjectAssignment[];
  created_at?: string;
  /** Which teams participate in this project. "all" | [] (excludes all) | list of team ids. */
  included_teams?: "all" | string[];
  /** When set, items touching other teams' workspaces or exceeding this threshold escalate. */
  escalation_threshold?: "never" | "cross_team" | "cross_team_or_flagged";
};

const PROJECTS_PATH =
  process.env.BUSINESS_PROJECTS_PATH ?? join(CONFIG_DIR, "projects.json");
const TEAMS_PATH = join(CONFIG_DIR, "teams.json");

export function getProjects(): Project[] {
  if (!existsSync(PROJECTS_PATH)) return [];
  try {
    const raw = JSON.parse(readFileSync(PROJECTS_PATH, "utf8"));
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

export function getProject(id: string): Project | null {
  return getProjects().find((p) => p.id === id) ?? null;
}

export function saveProject(input: {
  id?: string;
  name: string;
  folder: string;
  assignments?: ProjectAssignment[];
}): Project {
  const folder = resolveWorkspace(input.folder);
  if (!folder) throw new Error("folder is required");
  if (!input.name?.trim()) throw new Error("name is required");

  const projects = getProjects();
  const id =
    input.id ??
    `proj_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  const validRoles = [...BUSINESS_ROLES, "Member"] as const;

  const project: Project = {
    id,
    name: input.name.trim(),
    folder,
    assignments: (input.assignments ?? []).filter(
      (a) =>
        getCharacter(a.character_id) &&
        (validRoles as readonly string[]).includes(a.role),
    ),
    created_at:
      projects.find((p) => p.id === id)?.created_at ?? new Date().toISOString(),
  };

  const idx = projects.findIndex((p) => p.id === id);
  if (idx >= 0) projects[idx] = project;
  else projects.push(project);

  ensureConfigDir();
  writeFileSync(PROJECTS_PATH, JSON.stringify(projects, null, 2));
  return project;
}

export function deleteProject(id: string): boolean {
  const projects = getProjects();
  const next = projects.filter((p) => p.id !== id);
  if (next.length === projects.length) return false;
  writeFileSync(PROJECTS_PATH, JSON.stringify(next, null, 2));
  // Clear active pointer if it referenced this project
  if (getSettings().active_project === id) {
    saveSettings({ active_project: null });
  }
  return true;
}

/** The active project (settings.active_project), if any. */
export function activeProject(): Project | null {
  const id = getSettings().active_project;
  return id ? getProject(id) : null;
}

// ── Teams (multi-team orchestration) ──────────────────────────────────────────

export type TeamRole = "lead" | "pm" | "engineer" | "researcher" | "judge";

export type DailyCycle = {
  enabled: boolean;
  iterations: number;
  schedule: string;
  branch_strategy: string;
  auto_commit: boolean;
  requires_review_panel: boolean;
};

export type Team = {
  id: string;
  name: string;
  workspace: string;
  selection_mode: "round_robin" | "random" | "manual";
  roles: Record<TeamRole, string[]>;
  skills?: string[];
  wiki_page?: string;
  transcript_dir?: string;
  daily_cycle?: DailyCycle;
};

export type TopJudge = {
  character: string;
  description?: string;
};

export type Orchestrator = {
  character: string;
  mode: "fan_out_fan_in" | "sequential" | "parallel";
  team_selection: "all" | "subset" | "single";
  description?: string;
};

export type TeamsConfig = {
  teams: Team[];
  orchestrator: Orchestrator;
  top_judge?: TopJudge;
};

export function getTeamsConfig(): TeamsConfig {
  if (!existsSync(TEAMS_PATH)) {
    return { teams: [], orchestrator: { character: "general_vector", mode: "fan_out_fan_in", team_selection: "all" }, top_judge: { character: "solomon_hart" } };
  }
  try {
    return JSON.parse(readFileSync(TEAMS_PATH, "utf8"));
  } catch {
    return { teams: [], orchestrator: { character: "general_vector", mode: "fan_out_fan_in", team_selection: "all" }, top_judge: { character: "solomon_hart" } };
  }
}

export function saveTeamsConfig(config: TeamsConfig): void {
  ensureConfigDir();
  writeFileSync(TEAMS_PATH, JSON.stringify(config, null, 2));
}

export function getTeam(id: string): Team | null {
  return getTeamsConfig().teams.find((t) => t.id === id) ?? null;
}

export function getTeamMembers(team: Team): string[] {
  const all = new Set<string>();
  for (const members of Object.values(team.roles)) {
    for (const id of members) all.add(id);
  }
  return [...all];
}

export function getOrchestrator(): Orchestrator {
  return getTeamsConfig().orchestrator;
}

export function getTopJudge(): TopJudge {
  return getTeamsConfig().top_judge ?? { character: "solomon_hart" };
}

/** Select the next character for a team role using the team's selection mode. */
export function selectNextCharacter(team: Team, role: TeamRole): string | null {
  const members = team.roles[role];
  if (!members.length) return null;
  if (team.selection_mode === "random") {
    return members[Math.floor(Math.random() * members.length)];
  }
  // round_robin: use a simple counter based on timestamp
  const idx = Math.floor(Date.now() / 1000) % members.length;
  return members[idx];
}

// ── Settings ──────────────────────────────────────────────────────────────────

export function getSettings(): BusinessSettings {
  if (!existsSync(SETTINGS_PATH)) return { ...DEFAULT_SETTINGS };
  try {
    const saved = JSON.parse(readFileSync(SETTINGS_PATH, "utf8"));
    return { ...DEFAULT_SETTINGS, ...saved };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export function saveSettings(patch: Partial<BusinessSettings>): BusinessSettings {
  const merged = { ...getSettings(), ...patch };
  // Clamp / validate
  merged.temperature = Math.min(2, Math.max(0, Number(merged.temperature) || 0));
  merged.max_tokens = Math.min(4096, Math.max(64, Number(merged.max_tokens) || 500));
  merged.history_turns = Math.min(20, Math.max(0, Number(merged.history_turns) || 6));
  merged.rag_k = Math.min(20, Math.max(1, Number(merged.rag_k) || 5));
  merged.dispatch_timeout_seconds = Math.min(
    7200, Math.max(30, Number(merged.dispatch_timeout_seconds) || 900),
  );
  merged.dispatch_max_retries = Math.min(4, Math.max(0, Number(merged.dispatch_max_retries) || 1));
  merged.dispatch_max_parallel = Math.min(8, Math.max(1, Number(merged.dispatch_max_parallel) || 2));
  merged.team_review = Boolean(merged.team_review);
  ensureConfigDir();
  writeFileSync(SETTINGS_PATH, JSON.stringify(merged, null, 2));
  return merged;
}

// ── Hybrid RAG context ────────────────────────────────────────────────────────

const RAG_URL = process.env.RAG_SERVER_URL ?? "http://127.0.0.1:5080";
const LLM_BASE =
  process.env.FREELLM_API_BASE ?? process.env.OPENAI_API_BASE ?? "http://127.0.0.1:3001/v1";
const LLM_MODEL_ENV = process.env.FREELLM_MODEL ?? process.env.LLM_MODEL;

/** Unified API key for the local FreeLLM proxy: env override, else its SQLite DB. */
function freellmKey(): string {
  if (process.env.FREELLM_API_KEY) return process.env.FREELLM_API_KEY;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Database = require("better-sqlite3");
    const dbPath = join(MONOREPO_ROOT, "server", "data", "freeapi.db");
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

export async function ragContext(query: string, k = 5): Promise<string> {
  try {
    const res = await fetch(`${RAG_URL}/context`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, k }),
      signal: AbortSignal.timeout(15_000),
    });
    if (!res.ok) return "";
    const data = (await res.json()) as { context?: string };
    return data.context?.trim() ? `\n\n${data.context.trim()}\n` : "";
  } catch {
    return "";
  }
}

// ── Generation ────────────────────────────────────────────────────────────────

export type ChatTurn = { speaker: string; text: string };

export async function generateTurn(opts: {
  systemPrompt: string;
  topic: string;
  history: ChatTurn[];
  userName?: string;
  settings?: BusinessSettings;
}): Promise<{ text: string; model: string }> {
  const s = opts.settings ?? getSettings();

  const messages: Array<{ role: string; content: string }> = [
    {
      role: "system",
      content:
        opts.systemPrompt +
        `\n\nYou are speaking in a team working session about: "${opts.topic}".` +
        (opts.userName ? ` The human leading the session is ${opts.userName}.` : "") +
        `\nStay in character and in role. Be concise (under 180 words). Address teammates by name when responding to them.`,
    },
  ];

  for (const turn of opts.history.slice(-s.history_turns)) {
    messages.push({
      role: turn.speaker === opts.userName ? "user" : "assistant",
      content: `${turn.speaker}: ${turn.text}`,
    });
  }

  const res = await fetch(`${LLM_BASE}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${freellmKey()}`,
    },
    body: JSON.stringify({
      model: LLM_MODEL_ENV ?? s.model,
      messages,
      temperature: s.temperature,
      max_tokens: s.max_tokens,
    }),
    signal: AbortSignal.timeout(120_000),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`LLM request failed (${res.status}): ${body.slice(0, 300)}`);
  }

  const data = (await res.json()) as {
    choices?: Array<{ message?: { content?: string } }>;
  };
  const text = data.choices?.[0]?.message?.content?.trim();
  if (!text) throw new Error("LLM returned empty response");
  return { text, model: LLM_MODEL_ENV ?? s.model };
}

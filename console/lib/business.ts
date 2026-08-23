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

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
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

export type Character = {
  id: string;
  name: string;
  image?: string;
  system_prompt?: string;
};

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
};

export const BUSINESS_ROLES = [
  "CTO",
  "PM",
  "Judge",
  "Researcher",
  "Engineer",
  "Analyst",
] as const;
export type BusinessRole = (typeof BUSINESS_ROLES)[number];

/** Role prompts are PREPENDED to whatever characters hold the role. */
export const ROLE_PROMPTS: Record<BusinessRole, string> = {
  CTO: `You are the Chief Technology Officer of the team. You own technical vision, architecture decisions, stack choices, and engineering risk. You evaluate ideas for feasibility, scalability, and maintainability. You push back on hype and ground every proposal in concrete trade-offs.`,
  PM: `You are the Project Manager of the team. You turn goals into plans: scope, milestones, subtasks, owners, and deadlines. You track risks and dependencies, ask the questions nobody asked, and keep debates converging toward shippable outcomes.`,
  Judge: `You are the impartial Judge of the team. You weigh all arguments presented, identify the strongest reasoning and the weakest assumptions, and deliver clear verdicts. When asked for a decision you produce a structured ruling: decision, rationale, rejected alternatives, and next actions.`,
  Researcher: `You are the Researcher of the team. You find, download, and study source material (books, papers, docs, transcripts), then bring cited evidence into the discussion. You distinguish verified facts from speculation and always state your sources.`,
  Engineer: `You are an Engineer of the team. You translate agreed designs into implementation details: file changes, interfaces, edge cases, tests. You flag anything ambiguous before writing code and prefer small verifiable steps.`,
  Analyst: `You are the Analyst of the team. You break down problems with data: metrics, trade-off tables, cost models, and risk assessments. You quantify claims and challenge hand-waving with numbers.`,
};

function ensureConfigDir() {
  mkdirSync(CONFIG_DIR, { recursive: true });
}

// ── Characters ────────────────────────────────────────────────────────────────

function readJsonArray(path: string): Character[] {
  if (!existsSync(path)) return [];
  try {
    const raw = JSON.parse(readFileSync(path, "utf8"));
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

export function listCharacters(): Character[] {
  const base = readJsonArray(CHARACTERS_PATH);
  const custom = readJsonArray(CUSTOM_CHARS_PATH);
  const seen = new Set(base.map((c) => c.id));
  return [...base, ...custom.filter((c) => !seen.has(c.id))];
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
  if (!(BUSINESS_ROLES as readonly string[]).includes(role)) {
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
  ensureConfigDir();
  writeFileSync(SETTINGS_PATH, JSON.stringify(merged, null, 2));
  return merged;
}

// ── Hybrid RAG context ────────────────────────────────────────────────────────

const RAG_URL = process.env.RAG_SERVER_URL ?? "http://localhost:5080";
const LLM_BASE =
  process.env.FREELLM_API_BASE ?? process.env.OPENAI_API_BASE ?? "http://localhost:3001/v1";
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

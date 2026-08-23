/**
 * Business team module.
 *
 * Bridges the console to:
 *   - services/debate/characters.json  (the AI character roster)
 *   - config/business/roles.json       (role → character assignments)
 *   - FreeLLM API (:3001/v1)           (LLM generation)
 *   - Hybrid RAG server (:5080)        (BM25 + embeddings context)
 *
 * A "role" (CTO, PM, Judge, Researcher, …) is layered ON TOP of a character:
 *   system prompt = ROLE_PROMPT[role] + "\n\n" + character.system_prompt
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

/** Monorepo root (console runs with cwd = <root>/console). */
export const MONOREPO_ROOT =
  process.env.BUSINESS_MONOREPO_ROOT ?? join(process.cwd(), "..");

const DEBATE_DIR = join(MONOREPO_ROOT, "services", "debate");
export const CHARACTERS_PATH = join(DEBATE_DIR, "characters.json");
export const IMAGES_DIR = join(DEBATE_DIR, "images");

const ROLES_PATH =
  process.env.BUSINESS_ROLES_PATH ??
  join(MONOREPO_ROOT, "config", "business", "roles.json");

export type Character = {
  id: string;
  name: string;
  image?: string;
  system_prompt?: string;
};

export type Roles = Record<string, string | null>;

export const BUSINESS_ROLES = [
  "CTO",
  "PM",
  "Judge",
  "Researcher",
  "Developer",
] as const;
export type BusinessRole = (typeof BUSINESS_ROLES)[number];

/** Role prompts are PREPENDED to whatever character holds the role. */
export const ROLE_PROMPTS: Record<BusinessRole, string> = {
  CTO: `You are the Chief Technology Officer of the team. You own technical vision, architecture decisions, stack choices, and engineering risk. You evaluate ideas for feasibility, scalability, and maintainability. You push back on hype and ground every proposal in concrete trade-offs.`,
  PM: `You are the Project Manager of the team. You turn goals into plans: scope, milestones, subtasks, owners, and deadlines. You track risks and dependencies, ask the questions nobody asked, and keep debates converging toward shippable outcomes.`,
  Judge: `You are the impartial Judge of the team. You weigh all arguments presented, identify the strongest reasoning and the weakest assumptions, and deliver clear verdicts. When asked for a decision you produce a structured ruling: decision, rationale, rejected alternatives, and next actions.`,
  Researcher: `You are the Researcher of the team. You find, download, and study source material (books, papers, docs, transcripts), then bring cited evidence into the discussion. You distinguish verified facts from speculation and always state your sources.`,
  Developer: `You are the Developer of the team. You translate agreed designs into implementation details: file changes, interfaces, edge cases, tests. You flag anything ambiguous before writing code and prefer small verifiable steps.`,
};

// ── Characters ────────────────────────────────────────────────────────────────

export function listCharacters(): Character[] {
  if (!existsSync(CHARACTERS_PATH)) return [];
  try {
    const raw = JSON.parse(readFileSync(CHARACTERS_PATH, "utf8"));
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

export function getCharacter(id: string): Character | null {
  return listCharacters().find((c) => c.id === id) ?? null;
}

// ── Role assignments ──────────────────────────────────────────────────────────

export function getRoles(): Roles {
  const roles: Roles = {};
  for (const r of BUSINESS_ROLES) roles[r] = null;
  if (!existsSync(ROLES_PATH)) return roles;
  try {
    const saved = JSON.parse(readFileSync(ROLES_PATH, "utf8")) as Roles;
    for (const r of BUSINESS_ROLES) {
      if (r in saved) roles[r] = saved[r];
    }
  } catch {
    /* corrupt file → defaults */
  }
  return roles;
}

export function assignRole(role: string, characterId: string | null): Roles {
  if (!(BUSINESS_ROLES as readonly string[]).includes(role)) {
    throw new Error(`Unknown role: ${role}`);
  }
  const roles = getRoles();
  roles[role] = characterId;
  mkdirSync(join(ROLES_PATH, ".."), { recursive: true });
  writeFileSync(ROLES_PATH, JSON.stringify(roles, null, 2));
  return roles;
}

/** Compose the final system prompt: role layer + character persona. */
export function composeSystemPrompt(role: BusinessRole, character: Character): string {
  return `${ROLE_PROMPTS[role]}\n\nYour name is ${character.name}. Your persona:\n${character.system_prompt ?? ""}`;
}

// ── Hybrid RAG context ────────────────────────────────────────────────────────

const RAG_URL = process.env.RAG_SERVER_URL ?? "http://localhost:5080";
const LLM_BASE =
  process.env.FREELLM_API_BASE ?? process.env.OPENAI_API_BASE ?? "http://localhost:3001/v1";
const LLM_MODEL = process.env.FREELLM_MODEL ?? process.env.LLM_MODEL ?? "llama3";

export async function ragContext(
  query: string,
  k = 5,
): Promise<string> {
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
}): Promise<{ text: string; model: string }> {
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

  // Re-inject recent history so each speaker tracks the conversation
  for (const turn of opts.history.slice(-6)) {
    messages.push({
      role: turn.speaker === opts.userName ? "user" : "assistant",
      content: `${turn.speaker}: ${turn.text}`,
    });
  }

  const res = await fetch(`${LLM_BASE}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.FREELLM_API_KEY ?? "not-needed"}`,
    },
    body: JSON.stringify({
      model: LLM_MODEL,
      messages,
      temperature: 0.8,
      max_tokens: 500,
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
  return { text, model: LLM_MODEL };
}

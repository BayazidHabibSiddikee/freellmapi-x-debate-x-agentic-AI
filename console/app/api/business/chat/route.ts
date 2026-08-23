import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import {
  getRoles,
  getSettings,
  getCharacter,
  composeSystemPrompt,
  ragContext,
  generateTurn,
  activeProject,
  type BusinessRole,
} from "@/lib/business";

/** Human instruction for what each role is allowed to DO — injected into prompts. */
const rosterCharacterIdByName = (name: string): string | undefined =>
  getCharacterList().find((c) => c.name === name)?.id;

function getCharacterList() {
  // lazy import cycle avoided: listCharacters re-exported here
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return (require("@/lib/business") as typeof import("@/lib/business")).listCharacters();
}
const ROLE_DUTIES: Record<string, string> = {
  Engineer:
    "Your job: turn decisions into code. Use the `code_task` tool to drive claude/opencode inside the project folder. Never hand-code in the debate — dispatch, then report results.",
  Researcher:
    "Your job: gather knowledge. Use `download_books` (web → PDFs → knowledge base), `study` (query the KB), `read_pdf`, and `read_project_docs`. Cite sources.",
  CTO: "Your job: technical verdicts. You may use any analysis tool (`study`, `web_search`, `read_project_docs`, `read_pdf`) but you do NOT write code yourself — you specify, Engineers implement.",
  PM: "Your job: scope and sequence. Use `read_project_docs` and `study` to understand state; break work into subtasks for others. You do not code.",
  Judge: "Your job: rule on arguments using evidence. Prefer `study` and `read_project_docs`; stay impartial; deliver structured verdicts.",
  Analyst: "Your job: quantify claims with data from `study`/`read_project_docs`. No coding.",
  Reviewer: "Your job: inspect delivered work. Use `read_project_docs` and `study` to verify claims against the codebase; report concrete findings with file references. You do not write code.",
  DevOps: "Your job: build/deploy/CI/monitoring. Like Engineers you may dispatch `code_task` (claude/opencode) — but only for infrastructure, pipelines, and automation work.",
  Security: "Your job: hunt vulnerabilities. Use `read_project_docs`, `read_pdf`, `web_search` (CVEs), `study`. Rank findings by severity. You never fix code yourself — you file findings for Engineers.",
  Writer: "Your job: document what was decided/built. Use `read_project_docs` and `study` for accuracy; draft docs and hand writing tasks to Engineers to commit. Precision over poetry.",
};

type Body = {
  topic?: string;
  history?: Array<{ speaker: string; text: string }>;
  role?: BusinessRole;        // speak as a member of this role
  character_id?: string;      // …or this exact character (overrides role)
  user_name?: string;
  use_rag?: boolean;
};

export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: Body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }

  const topic = body.topic?.trim();
  if (!topic) return NextResponse.json({ error: "topic is required" }, { status: 400 });
  const settings = getSettings();

  // Resolve the speaker:
  //   0. active project members (if a project is selected and staffed)
  //   1. explicit character_id
  //   2. requested role's members, round-robined by history length
  //   3. any assigned role's first member
  const project = activeProject();
  const projectStaffed = Boolean(project && project.assignments.length > 0);
  let role: BusinessRole | undefined = body.role;
  let characterId: string | undefined = body.character_id;

  if (!characterId && projectStaffed) {
    const list = project!.assignments;
    const pick = list[(body.history?.length ?? 0) % list.length];
    characterId = (
      body.role ? list.find((a) => a.role === body.role)?.character_id : undefined
    ) ?? pick.character_id;
    role = (list.find((a) => a.character_id === characterId)?.role ??
      "Member") as BusinessRole;
  }
  if (!characterId && role) {
    const cfg = getRoles()[role];
    characterId =
      cfg?.members.length
        ? cfg.members[(body.history?.length ?? 0) % cfg.members.length]
        : undefined;
  }
  if (!characterId && !projectStaffed) {
    const roles = getRoles();
    for (const [r, cfg] of Object.entries(roles)) {
      if (cfg.members.length) {
        role = r as BusinessRole;
        characterId = cfg.members[0];
        break;
      }
    }
  }

  if (!characterId) {
    return NextResponse.json(
      { error: "no speakers available — assign characters to roles or to the active project" },
      { status: 409 },
    );
  }
  const character = getCharacter(characterId);
  if (!character) {
    return NextResponse.json({ error: `character not found: ${characterId}` }, { status: 404 });
  }
  if (!role) role = "Engineer"; // fallback mandate for unassigned direct picks

  try {
    let knowledge = "";
    if (body.use_rag ?? settings.use_rag) {
      knowledge = await ragContext(topic, settings.rag_k);
    }

    // Peers: same-role members globally + other teammates on the active project
    const peerIds = new Set<string>(
      getRoles()[role]?.members.filter((id) => id !== character.id) ?? [],
    );
    for (const a of project?.assignments ?? []) {
      if (a.character_id !== character.id) peerIds.add(a.character_id);
    }
    const peers = [...peerIds]
      .map(getCharacter)
      .filter((c): c is NonNullable<typeof c> => Boolean(c));

    // Memory: what this character remembers — prioritized by teammates present
    let memCtx = "";
    try {
      const about = [...peerIds].join(",");
      const res = await fetch(
        `${process.env.AGENT_TOOLS_URL ?? "http://127.0.0.1:5090"}/persona/${character.id}/memory/context?limit=6&about=${encodeURIComponent(about)}`,
        { signal: AbortSignal.timeout(5_000) },
      );
      if (res.ok) {
        memCtx = ((await res.json()) as { context?: string }).context ?? "";
      }
    } catch {
      /* memory store down → proceed without */
    }

    const systemPrompt =
      composeSystemPrompt(role, character, peers) +
      (ROLE_DUTIES[role as string]
        ? `\n\nYour duty in this session: ${ROLE_DUTIES[role as string]}` +
          `\nTools you may ask the operator to run for you: ${character.tools?.length ? character.tools.join(", ") : "your role's defaults"}.`
        : "") +
      (memCtx ? `\n${memCtx}` : "") +
      (project
        ? `\n\nThe team's current project is "${project.name}", rooted at ${project.folder}. Keep discussion relevant to this codebase/folder.`
        : "") +
      (knowledge
        ? `\nUse this retrieved knowledge when relevant and name the source:\n${knowledge}`
        : "");

    const { text, model } = await generateTurn({
      systemPrompt,
      topic,
      history: Array.isArray(body.history) ? body.history : [],
      userName: body.user_name,
      settings,
    });

    // Learning: record this persona's stance; note who they were responding to
    const lastSpeaker = body.history?.[body.history.length - 1];
    const lastChar = lastSpeaker
      ? rosterCharacterIdByName(lastSpeaker.speaker)
      : undefined;
    fetch(
      `${process.env.AGENT_TOOLS_URL ?? "http://127.0.0.1:5090"}/persona/${character.id}/memory`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind: "teammate",
          content: `On "${topic.slice(0, 80)}" I argued: "${text.slice(0, 160)}"` +
            (lastChar && lastChar !== character.id
              ? ` — responding to ${lastSpeaker!.speaker}.`
              : ""),
          subject_id: lastChar ?? undefined,
        }),
        signal: AbortSignal.timeout(5_000),
      },
    ).catch(() => {});

    return NextResponse.json({
      speaker: character.name,
      role,
      character_id: character.id,
      text,
      model,
      used_rag: Boolean(knowledge),
    });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "generation failed" },
      { status: 502 },
    );
  }
}

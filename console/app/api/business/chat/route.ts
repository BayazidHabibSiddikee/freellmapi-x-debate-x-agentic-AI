import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import {
  getRoles,
  getSettings,
  getCharacter,
  composeSystemPrompt,
  ragContext,
  generateTurn,
  type BusinessRole,
} from "@/lib/business";

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
  //   1. explicit character_id
  //   2. requested role's members, round-robined by history length
  //   3. any assigned role's first member
  let role: BusinessRole | undefined = body.role;
  let characterId: string | undefined = body.character_id;

  if (!characterId && role) {
    const cfg = getRoles()[role];
    characterId =
      cfg?.members.length
        ? cfg.members[(body.history?.length ?? 0) % cfg.members.length]
        : undefined;
  }
  if (!characterId) {
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
      { error: "no characters assigned to any role yet — assign some in the Roles card" },
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

    // Peers sharing the same role (multi-member roles coordinate)
    const peers = role
      ? getRoles()[role].members
          .filter((id) => id !== character.id)
          .map(getCharacter)
          .filter((c): c is NonNullable<typeof c> => Boolean(c))
      : [];

    const systemPrompt =
      composeSystemPrompt(role, character, peers) +
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

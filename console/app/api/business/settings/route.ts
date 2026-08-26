import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import { getSettings, saveSettings, type BusinessSettings } from "@/lib/business";

// Explicit subset of BusinessSettings that PATCH may write.
type PatchableKeys = keyof BusinessSettings;
const ALLOWED_KEYS: PatchableKeys[] = [
  "model", "temperature", "max_tokens", "history_turns", "rag_k",
  "use_rag", "dispatch_agent_default", "dispatch_timeout_seconds",
  "allow_file_writes", "auto_review", "active_project", "telegram_bots",
  "dispatch_max_retries", "team_review", "dispatch_max_parallel",
];

export async function GET(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  return NextResponse.json(getSettings());
}

export async function PATCH(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let patch: Partial<BusinessSettings>;
  try {
    patch = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }

  const clean: Partial<BusinessSettings> = {};
  for (const key of ALLOWED_KEYS) {
    if (key in patch) (clean as Record<string, unknown>)[key] = patch[key];
  }

  return NextResponse.json(saveSettings(clean));
}

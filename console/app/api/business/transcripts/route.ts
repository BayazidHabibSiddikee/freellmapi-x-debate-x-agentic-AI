import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const HOME = process.env.HOME ?? "/root";
const TRANSCRIPTS_DIR = join(HOME, "swordoffice", "transcripts");

type TranscriptEntry = {
  team: string;
  filename: string;
  path: string;
  size: number;
  modified: string;
  preview: string;
};

function listTranscripts(): TranscriptEntry[] {
  const entries: TranscriptEntry[] = [];

  try {
    const teams = readdirSync(TRANSCRIPTS_DIR).filter(f =>
      statSync(join(TRANSCRIPTS_DIR, f)).isDirectory()
    );

    for (const team of teams) {
      const teamDir = join(TRANSCRIPTS_DIR, team);
      try {
        const files = readdirSync(teamDir)
          .filter(f => f.endsWith(".md"))
          .sort()
          .reverse()
          .slice(0, 5);

        for (const file of files) {
          const filePath = join(teamDir, file);
          const stat = statSync(filePath);
          const content = readFileSync(filePath, "utf-8");
          const preview = content.slice(0, 300).replace(/\n+/g, " ").trim();

          entries.push({
            team,
            filename: file,
            path: filePath,
            size: stat.size,
            modified: stat.mtime.toISOString(),
            preview,
          });
        }
      } catch { /* skip unreadable dirs */ }
    }
  } catch { /* dir doesn't exist */ }

  return entries.sort((a, b) => b.modified.localeCompare(a.modified));
}

function readTranscript(path: string): string | null {
  try {
    // Security: only allow reading from transcripts dir
    if (!path.startsWith(TRANSCRIPTS_DIR)) return null;
    return readFileSync(path, "utf-8");
  } catch {
    return null;
  }
}

/** GET: List recent transcripts. */
export async function GET(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const url = new URL(req.url);
  const action = url.searchParams.get("action") ?? "list";

  if (action === "list") {
    const transcripts = listTranscripts();
    return NextResponse.json({ ok: true, transcripts });
  }

  if (action === "read") {
    const path = url.searchParams.get("path");
    if (!path) return NextResponse.json({ error: "path required" }, { status: 400 });

    const content = readTranscript(path);
    if (content === null) {
      return NextResponse.json({ error: "file not found" }, { status: 404 });
    }
    return NextResponse.json({ ok: true, content });
  }

  return NextResponse.json({ error: "unknown action" }, { status: 400 });
}

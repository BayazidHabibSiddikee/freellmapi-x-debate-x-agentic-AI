import { NextRequest } from "next/server";
import { readFileSync, existsSync } from "fs";
import { join } from "path";
import { validateToken } from "@/lib/auth";

const PIPELINE_DIR = join(
  process.env.TEAM_DIR ??
    "/home/sword/freellmapi-x-debate-x-agentic-AI/config/business/teams/izuku-midoriya",
);
const PIPELINE_SCRIPT = join(PIPELINE_DIR, "scripts", "pipeline.py");
const OUTPUT_DIR = join(PIPELINE_DIR, "output");

export async function GET(req: NextRequest) {
  if (!(await validateToken(req))) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  // Return pipeline status: summary.json contents + whether script exists
  const summaryPath = join(OUTPUT_DIR, "summary.json");
  let summary: unknown[] = [];
  if (existsSync(summaryPath)) {
    try {
      summary = JSON.parse(readFileSync(summaryPath, "utf8"));
    } catch {
      summary = [];
    }
  }

  return Response.json({
    ok: true,
    script_exists: existsSync(PIPELINE_SCRIPT),
    team_dir: PIPELINE_DIR,
    iterations_done: summary.length,
    summary,
  });
}

export async function POST(req: NextRequest) {
  if (!(await validateToken(req))) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  const body = await req.json().catch(() => ({}));
  const action = (body as Record<string, unknown>).action ?? "run";

  if (action === "run") {
    // Spawn the pipeline as a detached background process
    const { spawn } = await import("child_process");
    const proc = spawn(
      "python3",
      [PIPELINE_SCRIPT],
      {
        detached: true,
        stdio: ["ignore", "pipe", "pipe"],
        cwd: PIPELINE_DIR,
      },
    );

    let stdout = "";
    let stderr = "";
    proc.stdout?.on("data", (d: Buffer) => { stdout += d.toString(); });
    proc.stderr?.on("data", (d: Buffer) => { stderr += d.toString(); });

    proc.unref();

    return Response.json({
      ok: true,
      pid: proc.pid,
      message: "Pipeline launched in background",
    });
  }

  if (action === "status") {
    const summaryPath = join(OUTPUT_DIR, "summary.json");
    let summary: unknown[] = [];
    if (existsSync(summaryPath)) {
      try {
        summary = JSON.parse(readFileSync(summaryPath, "utf8"));
      } catch {
        summary = [];
      }
    }
    return Response.json({ ok: true, iterations_done: summary.length, summary });
  }

  if (action === "reset") {
    // Clear output for a fresh run
    const { execSync } = await import("child_process");
    try {
      execSync(`rm -rf "${join(OUTPUT_DIR, "*")}"`, { stdio: "ignore" });
    } catch {
      // best-effort
    }
    return Response.json({ ok: true, message: "Output cleared" });
  }

  return Response.json({ error: "unknown action" }, { status: 400 });
}

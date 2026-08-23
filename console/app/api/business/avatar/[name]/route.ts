import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import { IMAGES_DIR } from "@/lib/business";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, normalize } from "node:path";

const MIME: Record<string, string> = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".gif": "image/gif",
};

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ name: string }> },
) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const { name } = await ctx.params;
  const safe = normalize(name).replace(/^(\.\.[/\\])+/, "");
  if (safe.includes("/") || safe.includes("\\")) {
    return NextResponse.json({ error: "bad path" }, { status: 400 });
  }

  const ext = safe.slice(safe.lastIndexOf(".")).toLowerCase();
  const contentType = MIME[ext];
  if (!contentType) return NextResponse.json({ error: "unsupported type" }, { status: 400 });

  // Characters may reference either the bare name or a .card.png variant
  const candidates = [
    join(IMAGES_DIR, safe),
    join(IMAGES_DIR, `${safe}.card.png`),
    join(IMAGES_DIR, safe.replace(/\.card\.png$/, ".png")),
  ];
  const path = candidates.find((p) => existsSync(p) && statSync(p).isFile());
  if (!path) return NextResponse.json({ error: "not found" }, { status: 404 });

  const buf = readFileSync(path);
  return new NextResponse(new Uint8Array(buf), {
    headers: {
      "Content-Type": contentType,
      "Cache-Control": "public, max-age=86400",
    },
  });
}

import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import { getConfig, updateConfig } from "@/lib/config";

export async function GET() {
  return NextResponse.json(getConfig());
}

export async function POST(req: NextRequest) {
  if (!validateToken(req)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  try {
    const { key, value } = await req.json();
    if (!key) return NextResponse.json({ error: "key is required" }, { status: 400 });

    const newConfig = await updateConfig(key, value);
    return NextResponse.json(newConfig);
  } catch (e) {
    return NextResponse.json({ error: "failed to update config" }, { status: 500 });
  }
}

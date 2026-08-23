import { NextRequest, NextResponse } from "next/server";
import { validateToken } from "@/lib/auth";
import {
  getProjects,
  saveProject,
  deleteProject,
  type ProjectAssignment,
} from "@/lib/business";

export async function GET(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  return NextResponse.json({ projects: getProjects() });
}

type Body = {
  id?: string;
  name?: string;
  folder?: string;
  assignments?: ProjectAssignment[];
};

export async function POST(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: Body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }
  if (!body.name?.trim() || !body.folder?.trim()) {
    return NextResponse.json({ error: "name and folder are required" }, { status: 400 });
  }

  try {
    const project = saveProject({
      id: body.id,
      name: body.name,
      folder: body.folder,
      assignments: body.assignments ?? [],
    });
    return NextResponse.json({ ok: true, project });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "save failed" },
      { status: 400 },
    );
  }
}

export async function DELETE(req: NextRequest) {
  if (!validateToken(req)) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const id = req.nextUrl.searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id is required" }, { status: 400 });
  const ok = deleteProject(id);
  return NextResponse.json({ ok }, { status: ok ? 200 : 404 });
}

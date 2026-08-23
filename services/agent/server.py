"""
services/agent/server.py — tool execution API for the Business team (port 5090).

Endpoints:
  GET  /tools?role=Researcher   → tools available to a role
  POST /execute                 → {tool, args, role} — validated + executed
  GET  /report                  → registry status / import errors
  GET  /health
"""

import asyncio
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tools_registry import execute, list_tools, report, ToolError

app = FastAPI(title="Business Agent Tools", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExecuteRequest(BaseModel):
    tool: str
    args: Dict[str, Any] = {}
    role: Optional[str] = None


@app.get("/health")
async def health():
    return {"status": "operational", "port": 5090}


@app.get("/tools")
async def tools(role: Optional[str] = None):
    return {"tools": list_tools(role), "role": role}


@app.post("/execute")
async def run_tool(req: ExecuteRequest):
    try:
        result = await asyncio.to_thread(execute, req.tool, req.args, req.role)
        return {"ok": True, "tool": req.tool, "role": req.role, "result": result}
    except ToolError as e:
        return {"ok": False, "tool": req.tool, "error": str(e), "kind": "validation"}
    except Exception as e:  # noqa: BLE001 — surface remote/tool failures to caller
        return {"ok": False, "tool": req.tool, "error": str(e)[:500], "kind": "execution"}


@app.get("/report")
async def get_report():
    return report()


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5090)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port)

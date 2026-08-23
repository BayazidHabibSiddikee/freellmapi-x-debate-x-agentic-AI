"""
agent_master.py  –  Async Multi-Agent Orchestrator
====================================================

Architecture
------------
 ┌──────────────────────────────────────────────────────┐
 │                     MasterAgent                      │
 │  • Decomposes task into subtasks                     │
 │  • Fans out subtasks to SubAgents (async, parallel)  │
 │  • Waits for ALL reports before doing anything       │
 │  • Runs an iterative review loop (default 2 passes)  │
 │  • Each pass: finds issues → fans them back out      │
 │  • Synthesises final answer after all passes done    │
 └──────────────────────────────────────────────────────┘

Key changes vs original
-----------------------
1. Subagents run fully ASYNC/PARALLEL (asyncio + ThreadPoolExecutor).
   MasterAgent never processes anything until every subagent reports in.
2. After the initial parallel execution round, the master reviews all
   outputs and extracts per-subtask issues.
3. Issues are fanned back out to subagents (async/parallel again) for a
   fix pass.
4. The whole review→fix loop runs `review_passes` times (default 2).
5. Fallback chain unchanged: tries preferred agent, then all others.

Usage
-----
    python agent_master.py "Write a merge-sorted-lists function in Python"

    # custom passes / orchestrator
    agent = MasterAgent(orchestrator="claude", review_passes=2, verbose=True)
    result = asyncio.run(agent.execute_task("...your task..."))
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────
#  Data Structures
# ─────────────────────────────────────────────────────────────────

@dataclass
class Subtask:
    id: int
    description: str
    type: str                       # write | review | debug | general
    depends_on: List[int] = field(default_factory=list)
    assigned_agent: str = ""
    status: str = "pending"         # pending | running | done | failed
    output: str = ""
    error: str = ""


@dataclass
class AgentReport:
    """Single execution report from one subagent."""
    agent: str
    subtask_id: int
    pass_number: int                # which review pass (0 = initial)
    output: str
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class IssueFixRequest:
    """Master sends this to a subagent after reviewing pass N outputs."""
    subtask_id: int
    original_description: str
    previous_output: str
    issues: List[str]


# ─────────────────────────────────────────────────────────────────
#  Agent invocation strategies
# ─────────────────────────────────────────────────────────────────

AGENT_STRATEGIES: Dict[str, dict] = {
    "claude":     {"mode": "flag",   "args": ["-p"]},
    "openclaude": {"mode": "flag",   "args": ["-p"]},
    "opencode":   {"mode": "subarg", "args": ["run"]},
    "gemini":     {"mode": "flag",   "args": ["-p"]},
    "kiro-cli":   {"mode": "stdin",  "args": ["chat"]},
}

AGENT_TIMEOUTS: Dict[str, int] = {
    "claude":     60,
    "openclaude": 60,
    "opencode":   45,
    "gemini":     60,
    "kiro-cli":   60,
}

STAGE_ROLES: Dict[str, str] = {
    "write":   "You are a senior software engineer. Write clean, well-documented code.",
    "review":  "You are a code reviewer. Identify bugs, style issues, and improvements.",
    "debug":   "You are a debugging expert. Fix errors and explain what was wrong.",
    "general": "You are a helpful assistant. Complete the task as best you can.",
    "fix":     "You are a software engineer fixing previously identified issues. "
               "Address every issue listed and return the corrected output.",
}


# ─────────────────────────────────────────────────────────────────
#  Low-level CLI helpers  (sync – called from a thread)
# ─────────────────────────────────────────────────────────────────

def _call_agent_sync(agent: str, prompt: str) -> str:
    """
    Blocking call to one CLI agent.
    Returns the output string, or "[ERROR] ..." / "[SKIP] ..." on failure.
    Never raises.
    """
    if shutil.which(agent) is None:
        return f"[SKIP] Agent '{agent}' not found in PATH."

    strategy = AGENT_STRATEGIES.get(agent, {"mode": "flag", "args": ["-p"]})
    timeout  = AGENT_TIMEOUTS.get(agent, 60)
    mode     = strategy["mode"]
    args     = strategy["args"]

    try:
        if mode in ("flag", "subarg"):
            cmd    = [agent] + args + [prompt]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        elif mode == "stdin":
            cmd    = [agent] + args
            result = subprocess.run(cmd, input=prompt, capture_output=True,
                                    text=True, timeout=timeout)
        else:
            return f"[ERROR] Unknown strategy mode '{mode}' for agent '{agent}'."

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        output = stdout if stdout else stderr

        if not output:
            return f"[ERROR] {agent}: empty response (exit {result.returncode})"
        return output

    except subprocess.TimeoutExpired:
        return f"[ERROR] Agent '{agent}' timed out after {timeout}s."
    except Exception as exc:
        return f"[ERROR] {agent}: {exc}"


def _call_with_fallback_sync(
    preferred: str,
    prompt: str,
    pool: List[str],
) -> Tuple[str, str]:
    """
    Try preferred agent; on any error cycle through pool.
    Returns (agent_name_used, output).
    """
    candidates = [preferred] + [a for a in pool if a != preferred]
    for agent in candidates:
        out = _call_agent_sync(agent, prompt)
        if not (out.startswith("[ERROR]") or out.startswith("[SKIP]")):
            return agent, out
    return preferred, "[ERROR] All agents failed to respond."


# ─────────────────────────────────────────────────────────────────
#  MasterAgent
# ─────────────────────────────────────────────────────────────────

class MasterAgent:
    """
    Async orchestrator.

    Flow
    ----
    execute_task()
        │
        ├─ decompose_task()          → List[Subtask]
        │
        ├─ [PASS 0] _run_subtasks_parallel()
        │       → fan-out: all subtasks execute simultaneously
        │       → fan-in:  master waits for EVERY report
        │
        ├─ for pass in range(review_passes):          ← iterative loop
        │       _review_all_outputs()
        │           → master inspects every output, lists per-subtask issues
        │       _run_fix_pass_parallel()
        │           → fan-out: only subtasks WITH issues get a fix prompt
        │           → fan-in:  master waits for all fix reports
        │
        └─ _synthesise()             → final consolidated answer
    """

    AGENT_POOL: List[str] = ["claude", "openclaude", "opencode", "gemini", "kiro-cli"]

    def __init__(
        self,
        orchestrator: str = "opencode",
        review_passes: int = 2,
        max_workers: int = 8,
        verbose: bool = True,
        callback=None,
    ):
        self.orchestrator   = orchestrator
        self.review_passes  = review_passes
        self.max_workers    = max_workers
        self.verbose        = verbose
        self.callback       = callback
        self._rr_index      = 0
        self.history: List[AgentReport] = []

    # ── Logging ──────────────────────────────────────────────────

    def log(self, msg: str, level: str = "INFO") -> None:
        tag      = {"INFO": "[*]", "WARN": "[!]", "ERR": "[✗]", "OK": "[✓]"}.get(level, "[?]")
        full_msg = f"{tag} {msg}"
        if self.verbose:
            print(full_msg)
        if self.callback:
            self.callback(full_msg)

    # ── Agent pool ────────────────────────────────────────────────

    def available_agents(self) -> List[str]:
        return [a for a in self.AGENT_POOL if shutil.which(a) is not None]

    def _pick_agent(self) -> str:
        """Round-robin over available agents."""
        pool = self.available_agents()
        if not pool:
            raise RuntimeError(
                "No CLI agents found in PATH. Need at least one of: " +
                ", ".join(self.AGENT_POOL)
            )
        agent = pool[self._rr_index % len(pool)]
        self._rr_index += 1
        return agent

    # ── Async wrapper around sync CLI call ────────────────────────

    async def _async_call(
        self,
        preferred: str,
        prompt: str,
        executor: ThreadPoolExecutor,
    ) -> Tuple[str, str]:
        """
        Run the blocking CLI call inside a thread so the event loop
        stays free and all subagents truly run in parallel.
        """
        loop = asyncio.get_running_loop()
        pool = self.available_agents()
        return await loop.run_in_executor(
            executor,
            _call_with_fallback_sync,
            preferred,
            prompt,
            pool,
        )

    # ── Task decomposition (sync – called once) ───────────────────

    async def decompose_task(
        self,
        task: str,
        executor: ThreadPoolExecutor,
    ) -> List[Subtask]:
        self.log(f"Decomposing task via orchestrator '{self.orchestrator}' …")

        prompt = (
            "Break this coding task into subtasks (write→review→debug order).\n"
            "Reply ONLY with a JSON array – no markdown, no preamble.\n"
            'Schema: [{"id":1,"description":"...","type":"write|review|debug|general","depends_on":[]}]\n\n'
            f"Task: {task}"
        )

        agent_used, raw = await self._async_call(self.orchestrator, prompt, executor)
        self.log(f"Decompose response from '{agent_used}':\n{raw}")

        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            raw = match.group(0)

        try:
            items    = json.loads(raw)
            subtasks = [
                Subtask(
                    id          = item["id"],
                    description = item["description"],
                    type        = item.get("type", "general"),
                    depends_on  = item.get("depends_on", []),
                )
                for item in items
            ]
            self.log(f"Decomposed into {len(subtasks)} subtask(s).", "OK")
            return subtasks
        except (json.JSONDecodeError, KeyError) as exc:
            self.log(f"Could not parse subtasks ({exc}). Falling back to single subtask.", "WARN")
            return [Subtask(id=1, description=task, type="general")]

    # ── PASS 0: initial parallel execution ───────────────────────

    async def _run_subtasks_parallel(
        self,
        subtasks: List[Subtask],
        completed: Dict[int, str],
        pass_number: int,
        executor: ThreadPoolExecutor,
    ) -> None:
        """
        Fan-out: launch all subtasks concurrently.
        Fan-in:  await ALL before returning.
        Results are written into `completed` and `self.history`.
        """
        self.log(
            f"[Pass {pass_number}] Fanning out {len(subtasks)} subtask(s) in parallel …"
        )

        async def _run_one(subtask: Subtask) -> None:
            preferred = self._pick_agent()
            subtask.assigned_agent = preferred
            subtask.status = "running"

            role = STAGE_ROLES.get(subtask.type, STAGE_ROLES["general"])
            dep_ctx = "".join(
                f"\n--- Output of subtask {d} ---\n{completed[d]}\n"
                for d in subtask.depends_on
                if d in completed
            )
            prompt = "\n".join(filter(None, [
                role,
                f"\nSubtask: {subtask.description}",
                f"\nContext / previous output:\n{dep_ctx}" if dep_ctx else "",
            ]))

            self.log(f"  → Subtask {subtask.id} ({subtask.type}) starting on '{preferred}'")
            agent_used, output = await self._async_call(preferred, prompt, executor)

            success                = not output.startswith("[ERROR]")
            subtask.status         = "done" if success else "failed"
            subtask.output         = output
            subtask.assigned_agent = agent_used
            if not success:
                subtask.error = output

            completed[subtask.id] = output
            self.history.append(AgentReport(
                agent       = agent_used,
                subtask_id  = subtask.id,
                pass_number = pass_number,
                output      = output,
                success     = success,
            ))
            status_tag = "OK" if success else "ERR"
            self.log(f"  ✓ Subtask {subtask.id} finished on '{agent_used}'.", status_tag)

        await asyncio.gather(*(_run_one(st) for st in subtasks))
        self.log(f"[Pass {pass_number}] All {len(subtasks)} subagents reported in. Master reviewing …", "OK")

    # ── Review: master inspects all outputs ──────────────────────

    async def _review_all_outputs(
        self,
        task: str,
        subtasks: List[Subtask],
        completed: Dict[int, str],
        pass_number: int,
        executor: ThreadPoolExecutor,
    ) -> Dict[int, List[str]]:
        """
        Master agent reviews every subtask output and returns a dict:
            { subtask_id: [issue1, issue2, ...] }
        Subtasks with no issues get an empty list → skipped in fix pass.
        """
        self.log(f"[Review {pass_number}] Master reviewing all outputs …")

        outputs_block = "\n\n".join(
            f"=== Subtask {st.id} ({st.type}): {st.description} ===\n"
            f"{completed.get(st.id, '[no output]')}"
            for st in subtasks
        )

        review_prompt = (
            f"You are the master orchestrator performing review pass {pass_number}.\n"
            f"Original task: {task}\n\n"
            f"Below are the current outputs from all subagents:\n\n"
            f"{outputs_block}\n\n"
            "For EACH subtask, list any concrete issues (bugs, missing logic, style violations, "
            "incomplete answers, etc.).\n"
            "Reply ONLY with a JSON object – no markdown, no preamble.\n"
            'Schema: {"subtask_id": ["issue1", "issue2"], ...}\n'
            'Use an empty array [] if a subtask has no issues.'
        )

        agent_used, raw = await self._async_call(self.orchestrator, review_prompt, executor)
        self.log(f"  Review response from '{agent_used}':\n{raw}")

        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            raw = match.group(0)

        try:
            issues_map_raw: Dict[str, list] = json.loads(raw)
            # Normalise keys to int
            issues_map = {int(k): v for k, v in issues_map_raw.items()}
            total_issues = sum(len(v) for v in issues_map.values())
            self.log(
                f"[Review {pass_number}] Found {total_issues} issue(s) across "
                f"{sum(1 for v in issues_map.values() if v)} subtask(s).",
                "WARN" if total_issues else "OK",
            )
            return issues_map
        except (json.JSONDecodeError, ValueError) as exc:
            self.log(f"Could not parse review JSON ({exc}). Skipping fix pass.", "WARN")
            return {}

    # ── Fix pass: parallel re-execution for flawed subtasks ──────

    async def _run_fix_pass_parallel(
        self,
        subtasks: List[Subtask],
        completed: Dict[int, str],
        issues_map: Dict[int, List[str]],
        pass_number: int,
        executor: ThreadPoolExecutor,
    ) -> None:
        """
        For every subtask that has issues, fan out a fix prompt in parallel.
        Subtasks with no issues are left untouched.
        Fan-in: wait for ALL fix agents before returning.
        """
        fix_targets = [st for st in subtasks if issues_map.get(st.id)]

        if not fix_targets:
            self.log(f"[Fix Pass {pass_number}] No issues to fix. Skipping.", "OK")
            return

        self.log(
            f"[Fix Pass {pass_number}] Fanning out fixes for "
            f"{len(fix_targets)} subtask(s) in parallel …"
        )

        async def _fix_one(subtask: Subtask) -> None:
            issues    = issues_map[subtask.id]
            preferred = self._pick_agent()

            issues_text = "\n".join(f"  - {iss}" for iss in issues)
            prompt = (
                f"{STAGE_ROLES['fix']}\n\n"
                f"Original subtask: {subtask.description}\n\n"
                f"Your previous output:\n{completed.get(subtask.id, '[none]')}\n\n"
                f"Issues identified by the master reviewer:\n{issues_text}\n\n"
                "Please produce a corrected, complete output that resolves every issue."
            )

            self.log(f"  → Fixing subtask {subtask.id} on '{preferred}'")
            agent_used, output = await self._async_call(preferred, prompt, executor)

            success = not output.startswith("[ERROR]")
            if success:
                subtask.output         = output
                subtask.assigned_agent = agent_used
                subtask.status         = "done"
                completed[subtask.id]  = output
                self.log(f"  ✓ Subtask {subtask.id} fixed by '{agent_used}'.", "OK")
            else:
                self.log(f"  ✗ Fix for subtask {subtask.id} failed: {output}", "ERR")

            self.history.append(AgentReport(
                agent       = agent_used,
                subtask_id  = subtask.id,
                pass_number = pass_number,
                output      = output,
                success     = success,
            ))

        await asyncio.gather(*(_fix_one(st) for st in fix_targets))
        self.log(
            f"[Fix Pass {pass_number}] All fix agents reported in. Master resuming …", "OK"
        )

    # ── Final synthesis ───────────────────────────────────────────

    async def _synthesise(
        self,
        task: str,
        subtasks: List[Subtask],
        completed: Dict[int, str],
        executor: ThreadPoolExecutor,
    ) -> str:
        self.log("Synthesising final answer …")

        synthesis_input = "\n\n".join(
            f"=== Subtask {st.id}: {st.description} ===\n"
            f"Agent: {st.assigned_agent}\n{completed.get(st.id, '[no output]')}"
            for st in subtasks
        )
        prompt = (
            f"You are the final reviewer.\n"
            f"Original task: {task}\n\n"
            f"All agent outputs after {self.review_passes} review pass(es):\n\n"
            f"{synthesis_input}\n\n"
            "Produce a clean, final consolidated answer. "
            "Highlight any remaining unresolved issues."
        )
        _, final = await self._async_call(self.orchestrator, prompt, executor)
        return final

    # ── Main entry point ──────────────────────────────────────────

    async def execute_task(self, task: str) -> str:
        """
        Full pipeline:
          1. Decompose
          2. Pass 0 – initial parallel execution (all subagents)
          3. for i in range(review_passes):
               a. Master reviews all outputs        ← fan-in gate
               b. Fix pass – parallel fixes         ← fan-out + fan-in
          4. Synthesise
        """
        self.log(f"Task: {task}")

        pool = self.available_agents()
        if not pool:
            return "[ERROR] No CLI agents available. Install claude, opencode, or gemini."
        self.log(f"Available agents: {pool}")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:

            # ── Step 1: Decompose ──────────────────────────────────
            subtasks: List[Subtask] = await self.decompose_task(task, executor)

            completed: Dict[int, str] = {}

            # ── Step 2: Initial parallel execution ────────────────
            self.log("━" * 60)
            self.log("INITIAL PARALLEL EXECUTION (Pass 0)")
            self.log("━" * 60)
            await self._run_subtasks_parallel(subtasks, completed, pass_number=0, executor=executor)

            # ── Step 3: Iterative review + fix loop ───────────────
            for review_num in range(1, self.review_passes + 1):
                self.log("━" * 60)
                self.log(f"REVIEW + FIX LOOP  (iteration {review_num}/{self.review_passes})")
                self.log("━" * 60)

                # Master waits for all reports → then reviews
                issues_map = await self._review_all_outputs(
                    task, subtasks, completed, pass_number=review_num, executor=executor
                )

                # Fan back out to fix agents (async/parallel)
                await self._run_fix_pass_parallel(
                    subtasks, completed, issues_map, pass_number=review_num, executor=executor
                )

            # ── Step 4: Final synthesis ────────────────────────────
            self.log("━" * 60)
            self.log("FINAL SYNTHESIS")
            self.log("━" * 60)
            final = await self._synthesise(task, subtasks, completed, executor)

        self.log("All done.", "OK")
        return final

    # ── Summary report ────────────────────────────────────────────

    def print_summary(self) -> None:
        print("\n" + "═" * 60)
        print("  EXECUTION SUMMARY")
        print("═" * 60)
        for r in self.history:
            status = "✓" if r.success else "✗"
            print(
                f"  [{status}] Pass {r.pass_number}  "
                f"Subtask {r.subtask_id:02d}  "
                f"agent={r.agent:<12}  "
                f"ts={r.timestamp}"
            )
        print("═" * 60 + "\n")


# ─────────────────────────────────────────────────────────────────
#  CLI entry point
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "Write a Python function that merges two sorted lists. "
        "Review it for correctness and style, then debug any issues."
    )

    master       = MasterAgent(orchestrator="opencode", review_passes=2, verbose=True)
    final_answer = asyncio.run(master.execute_task(task))

    master.print_summary()

    print("\n" + "═" * 60)
    print("  FINAL ANSWER")
    print("═" * 60)
    print(final_answer)

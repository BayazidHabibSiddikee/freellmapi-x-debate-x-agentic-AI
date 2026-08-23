"""
services/agent/eval.py — deterministic micro-benchmark for the team pipeline.

Two arms, same tasks, programmatic verification:
  raw      → one headless `claude -p` shot at the task (baseline)
  pipeline → judge distills a mini-debate into a spec, then the Engineer
             dispatches via code_task (the full team flow)

Usage:
  ../debate/venv/bin/python eval.py --arm raw --tasks 3
  ../debate/venv/bin/python eval.py --arm pipeline --tasks 3
  ../debate/venv/bin/python eval.py --compare

Results: logs/eval_results.json + stdout table.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Tasks run in throwaway sandbox dirs — grant edit rights so headless agents
# can actually create/modify files there.
os.environ.setdefault("CLAUDE_FLAGS", "--permission-mode acceptEdits")

from dispatcher import _cli_for, resolve_workspace  # noqa: E402
from tools_registry import execute  # noqa: E402

EVAL_ROOT = Path.home() / "freellmapi-x-debate-x-agentic-AI"
RESULTS_PATH = EVAL_ROOT / "logs" / "eval_results.json"


# ── Tasks: setup(files) → prompt → verify(sandbox) raises on failure ──────────

def check_file_contains(fname: str, needle: str) -> Callable[[Path], None]:
    def verify(box: Path) -> None:
        content = (box / fname).read_text()
        assert needle in content, f"{fname} missing '{needle}'"
    return verify


def check_runs_printing(fname: str, expected: str) -> Callable[[Path], None]:
    def verify(box: Path) -> None:
        r = subprocess.run(
            [sys.executable, fname], cwd=box, capture_output=True, text=True, timeout=30
        )
        assert r.returncode == 0, f"exit {r.returncode}: {r.stderr[:200]}"
        assert expected in r.stdout, f"stdout lacked {expected!r}: got {r.stdout[:120]!r}"
    return verify


TASKS: List[Dict[str, Any]] = [
    {
        "id": "t1_greet",
        "setup": {},
        "prompt": "Create greet.py containing a function greet(name) that returns 'Hello, <name>!', and when run directly prints greet('World').",
        "verify": check_runs_printing("greet.py", "Hello, World!"),
    },
    {
        "id": "t2_fizz",
        "setup": {},
        "prompt": "Create fizzbuzz.py that prints numbers 1-15, replacing multiples of 3 with Fizz, 5 with Buzz, both with FizzBuzz — one per line.",
        "verify": lambda box: (
            lambda r: (
                None if b"FizzBuzz" in r.stdout and b"Fizz\n" in r.stdout and b"Buzz\n" in r.stdout
                else (_ for _ in ()).throw(AssertionError("fizzbuzz output wrong"))
            )
        )(
            subprocess.run([sys.executable, "fizzbuzz.py"], cwd=box, capture_output=True, timeout=30)
        ),
    },
    {
        "id": "t3_fix_bug",
        "setup": {
            "calc.py": (
                "def add(a, b):\n    return a - b  # TODO broken\n"
            )
        },
        "prompt": "calc.py has a bug: add(a,b) subtracts. Fix add to return the sum. Keep the file otherwise unchanged.",
        "verify": lambda box: (
            lambda r: (
                None if b"4" == r.stdout.strip() or "4" == r.stdout.strip()
                else (_ for _ in ()).throw(AssertionError(f"add(2,2) gave {r.stdout!r}"))
            )
        )(
            subprocess.run(
                [sys.executable, "-c", "import calc; print(calc.add(2,2))"],
                cwd=box, capture_output=True, text=True, timeout=30,
            )
        ),
    },
    {
        "id": "t4_readme",
        "setup": {
            "weather.py": (
                "def forecast(city):\n    \"\"\"Returns today's fake forecast string.\"\"\"\n"
                "    return f\"Sunny, 24C in {city}\"\n"
            )
        },
        "prompt": "Write README.md documenting weather.py: what it does, one usage example with output, in markdown.",
        "verify": check_file_contains("README.md", "forecast"),
    },
    {
        "id": "t5_json_util",
        "setup": {
            "data.json": '{"users": [{"name": "Ada", "age": 36}, {"name": "Kai", "age": 29}]}'
        },
        "prompt": "Create oldest_user.py that reads data.json and prints the name of the user with the highest age (expected: Ada).",
        "verify": check_runs_printing("oldest_user.py", "Ada"),
    },
]


# ── Arms ──────────────────────────────────────────────────────────────────────

def run_raw(task: Dict[str, Any], box: Path) -> str:
    """Baseline: bare headless claude, no team."""
    argv = _cli_for("claude")
    if argv is None:
        raise RuntimeError("claude CLI not found")
    proc = subprocess.run([*argv, task["prompt"]], cwd=box, capture_output=True,
                          text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exit {proc.returncode}")
    return proc.stdout


def run_pipeline(task: Dict[str, Any], box: Path) -> str:
    """Team flow: judge distills spec → engineer dispatches code_task in sandbox."""
    transcript = [
        {"speaker": "Sword", "text": task["prompt"]},
        {"speaker": "Ada the Architect",
         "text": "Keep the change minimal and verifiable; respect existing files in this folder."},
        {"speaker": "Priya Sharma",
         "text": "Single subtask, owner: Engineer, done when the verification passes."},
    ]
    from dispatcher import judge_spec
    spec = judge_spec(task["prompt"], transcript)
    # Force every subtask into the sandbox as cwd
    results = []
    for sub in spec.get("subtasks", [])[:3]:
        sub = {**sub, "cwd": str(box)}
        out = execute("code_task", {"prompt": sub["prompt"], "cwd": str(box),
                                    "agent": sub.get("agent", "claude")}, "Engineer")
        results.append(out)
    ok = [r for r in results if r.get("exit_code") == 0]
    if not ok:
        raise RuntimeError("all pipeline subtasks failed")
    return json.dumps(results)[:2000]


ARMS = {"raw": run_raw, "pipeline": run_pipeline}


# ── Runner ────────────────────────────────────────────────────────────────────

def run_eval(arm: str, n_tasks: int) -> List[Dict[str, Any]]:
    arm_fn = ARMS[arm]
    results = []
    for task in TASKS[:n_tasks]:
        run_id = uuid.uuid4().hex[:8]
        box = Path(resolve_workspace(str(EVAL_ROOT))) / "eval_sandbox" / f"{arm}_{run_id}"
        box.mkdir(parents=True, exist_ok=True)
        for fname, content in task["setup"].items():
            (box / fname).write_text(content)

        t0 = time.time()
        entry: Dict[str, Any] = {"task": task["id"], "arm": arm}
        try:
            arm_fn(task, box)
            elapsed = time.time() - t0
            try:
                task["verify"](box)
                entry.update(passed=True, seconds=round(elapsed, 1))
            except Exception as e:  # noqa: BLE001
                entry.update(passed=False, reason=f"verify: {e}", seconds=round(elapsed, 1))
        except Exception as e:  # noqa: BLE001
            entry.update(passed=False, reason=str(e)[:200],
                         seconds=round(time.time() - t0, 1))
        finally:
            shutil.rmtree(box, ignore_errors=True)
        results.append(entry)
        print(f"[{arm}] {task['id']}: {'✅ PASS' if entry['passed'] else '❌ FAIL'}"
              f" ({entry.get('seconds')}s{', ' + entry['reason'] if entry.get('reason') else ''})")
    return results


def save(results: List[Dict[str, Any]]) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing: List[Dict[str, Any]] = []
    if RESULTS_PATH.exists():
        try:
            existing = json.loads(RESULTS_PATH.read_text())
        except Exception:  # noqa: BLE001
            pass
    existing.extend(results)
    RESULTS_PATH.write_text(json.dumps(existing, indent=2))


def compare(n_tasks: int) -> None:
    all_r = run_eval("raw", n_tasks) + run_eval("pipeline", n_tasks)
    save(all_r)
    print("\n=== SUMMARY ===")
    for arm in ("raw", "pipeline"):
        rows = [r for r in all_r if r["arm"] == arm]
        passed = sum(1 for r in rows if r["passed"])
        avg = sum(r["seconds"] for r in rows) / max(len(rows), 1)
        print(f"{arm:9s}  {passed}/{len(rows)} pass   avg {avg:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["raw", "pipeline"])
    ap.add_argument("--tasks", type=int, default=5)
    ap.add_argument("--compare", action="store_true")
    args = ap.parse_args()

    if args.compare:
        compare(args.tasks)
    elif args.arm:
        save(run_eval(args.arm, args.tasks))
    else:
        ap.error("--arm or --compare required")

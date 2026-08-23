# 📊 BENCHMARK — How this system rates against agent-optimizing repos

Honest self-assessment against well-known GitHub projects that improve coding
agents, and against raw Claude Code with no orchestration.

## The landscape

| Repo | What it optimizes | Mechanism |
|---|---|---|
| [OpenHands](https://github.com/All-Hands-AI/OpenHands) | autonomous SWE agent loop | agent sandbox + planner/executor loop, SWE-bench harness |
| [SWE-agent](https://github.com/SWE-agent/SWE-agent) | terminal-native bug fixing | Agent-Computer Interface, guarded repo commands |
| [Aider](https://github.com/Aider-AI/aider) | edit quality via git discipline | repo-map, auto-commits, diff-format prompts |
| [MetaGPT](https://github.com/FoundationAgents/MetaGPT) | multi-role SOPs | role play (PM/architect/engineer) passing structured artifacts |
| [ChatDev](https://github.com/OpenBMB/ChatDev) | chat-chain company sim | two-agent phase transitions over a software lifecycle |
| [CrewAI / AutoGen](https://github.com/crewAIInc/crewAI) | multi-agent orchestration | crews/conversations with tool access per agent |
| **This repo** | **debate → judge → dispatch, grounded** | personas w/ per-person tool grants, hybrid RAG evidence, judge-distilled specs, headless claude/opencode execution |

## Where this system genuinely differs

1. **Evidence-grounded roles** — most multi-agent frameworks pass the same
   context to every role. Here each person pulls *cited* evidence from your own
   hybrid-RAG library (BM25 + embeddings fused via RRF) before opining.
2. **Hard tool gates, not prompt suggestions** — Engineers/DevOps hold
   `code_task`; Security/Reviewer/PM physically cannot write code. MetaGPT-style
   frameworks enforce roles via prompting; ours is enforced in the executor.
3. **One markdown file per person** (`config/business/personas/*.md`) — persona +
   individual tool grants, versionable, editable while services run.
4. **Judge artifact is machine-readable** — debates end in a JSON task spec
   validated before dispatch, not just "a summary".
5. **Human gate** — nothing touches your repos until you press Dispatch.

## Where others beat us (honest)

| Gap | Who does it better | Path to close |
|---|---|---|
| Standardized scores (SWE-bench etc.) | OpenHands, SWE-agent | wire our dispatcher into their harnesses (below) |
| Edit mechanics (diff formats, repo maps) | Aider | Aider already supports being the dispatched CLI |
| Autonomous long-horizon loops | OpenHands | deliberately out of scope: human-gated design |

## Ratings (1–5, qualitative, for THIS use case: small-team project work with human oversight)

| Criterion | Ours | Raw Claude Code | MetaGPT | CrewAI/AutoGen | OpenHands |
|---|---|---|---|---|---|
| Instruction quality before coding | **5** (debate+judge spec) | 2 (whatever you typed) | 4 (SOPs) | 3 | 3 |
| Evidence grounding (your docs/books) | **5** (hybrid RAG cited) | 2 (manual @files) | 1 | 2 | 1 |
| Role separation enforcement | **5** (executor-level gates) | n/a | 3 (prompted) | 3 (configured) | 2 |
| Coding power ceiling | 3 (delegates to claude/opencode) | **5** | 3 | 3 | **5** |
| Autonomy / unattended runs | 2 (human-gated by design) | 3 | 4 | 4 | **5** |
| Setup simplicity | **4** (one ./run.sh) | **5** | 2 | 3 | 2 |
| Observability of decisions | **4** (activity.jsonl + transcripts) | 2 | 2 | 3 | 3 |

**Net:** versus raw Claude, this trades some autonomy for dramatically better
task specification and auditable reasoning. Versus MetaGPT/CrewAI, it adds real
retrieval grounding and hard permission boundaries. Versus OpenHands, it is
easier to run locally but lacks their benchmark harness — until you connect it:

## Reproducible measurement (included)

Run the bundled micro-benchmark — same tasks through two arms, scored
programmatically:

```bash
cd services/agent && ../debate/venv/bin/python eval.py --tasks 5 --arm raw      # bare claude -p
cd services/agent && ../debate/venv/bin/python eval.py --tasks 5 --arm pipeline # judge→engineer→code_task
../debate/venv/bin/python eval.py --compare          # run both, print table
```

Results land in `logs/eval_results.json`. Tasks are deterministic file-manipulation
jobs verified by executable checks (script output, function correctness) — not
vibes. For heavyweight validation, point the dispatcher at
[SWE-bench](https://www.swebench.com/) instances: each instance's repo + issue text
becomes a subtask `prompt`, its FAIL_TO_PASS tests become the verifier.

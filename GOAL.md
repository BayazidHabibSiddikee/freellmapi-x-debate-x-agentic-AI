# 🎯 SwordOffice — Project Goal

## The problem

AI coding agents (Claude, OpenCode, Cursor, …) fail most often not because they
can't code, but because they're handed **vague, single-perspective instructions**.
One prompt → one model's guess → broken assumptions → hours of cleanup.

## The idea

> Don't send one AI to do a team's job. Let a **team of AI characters debate**,
> ground them in **your own knowledge**, let a **judge distill the verdict** into a
> precise task spec — and *then* hand that spec to the coding agents.

```
 you ──► CHARACTERS debate ──► JUDGE distills ──► CODING AGENTS execute
              ▲    (CTO/PM/…)        (task spec)      (claude/opencode)
              │                                            │
              └──────────── results reviewed by team ◄─────┘

                    all of it grounded by HYBRID RAG
                     (BM25 + embeddings, fused via RRF)
```

Characters aren't just roleplay — they're **structured perspectives**:

- A **CTO persona** evaluates architecture trade-offs before any code is written
- A **PM persona** turns goals into scoped subtasks with owners and deadlines
- An **Engineer persona** flags ambiguous requirements before implementation
- A **Researcher persona** downloads books/papers and cites your knowledge base
- A **Judge persona** weighs every argument and rules on the strongest reasoning
- A **Devil's Advocate** asks the question nobody asked

The output of the debate is not chat — it's a **machine-readable task spec**
(goal, decisions, self-contained subtasks) that coding agents execute headlessly,
with results fed back to the team for review.

## What "done" looks like

1. You open `/business`, assign characters to roles, pin workspaces under `~/`.
2. You describe a goal. The team debates it with cited context from your library.
3. You press **Judge**, review the spec, press **Dispatch**.
4. `claude` / `opencode` execute each subtask in its target repo.
5. The team reviews the diffs and loops until the judge approves.

The same team is reachable from anywhere through **Telegram** (`@kaggle_shot_bot`)
so a debate can happen while you're away from the desk.

## Principles

- **Local-first** — everything runs on your machine; your keys stay encrypted in
  the FreeLLM proxy; no cloud dependency except optional LLM providers.
- **Free-model routing** — 16+ free LLM providers behind one OpenAI-compatible
  endpoint; when one rate-limits, the router falls over to the next.
- **Grounded, not vibes** — debates cite the hybrid-RAG knowledge base built from
  documents you actually ingested (downloaded books, docs, transcripts).
- **Human in the loop** — dispatch is always an explicit button; agents never
  push code without you seeing the spec first.

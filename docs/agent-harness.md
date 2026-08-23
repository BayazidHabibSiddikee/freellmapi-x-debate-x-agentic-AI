# Agent Harness — freellmapi

Contracts for any agent (human or LLM) operating on this repository: how tools
are shaped, what observations look like, how failures recover, and what the
context budget is. Grounded in this codebase, not generic.

## 1. Action space

| Granularity | Operations | Rule |
|---|---|---|
| **Micro** (high-risk) | file ingest (`POST /business/api/upload`), `rag_delete_document`, anything touching `server/data/freeapi.db` or GitHub pushes | one operation per call, schema-validated input, explicit confirmation for destructive ops |
| **Medium** (common loop) | read/search/edit source, run tests, typecheck | batched freely |
| **Macro** (bulk) | multi-file sync between checkouts, dependency upgrades | only after a superset/additive diff check; never blind-overwrite |

Stable entry points:

- Typed agent tools: `server/src/mcp/rag-mcp-server.ts` (config:
  `mcp-configs/freellmapi-rag.json`) — `rag_search`, `rag_build_context`,
  `rag_list_documents`, `rag_get_document`, `rag_delete_document [DESTRUCTIVE]`.
- REST equivalents live under `/business/api/*` in
  `server/src/routes/business.ts`.

## 2. Observation contract

Every API response uses the envelope from `server/src/lib/envelope.ts`:

```jsonc
// success — legacy keys preserved at top level, payload mirrored under data
{ "success": true, "...payload": {}, "data": { "...payload" : {} } }

// failure — always carries a root-cause hint and a retry signal
{ "success": false, "error": "…", "hint": "how to fix / correct call shape", "retryable": false }
```

Every MCP tool call returns `{ success, data | error, retryable }` inside the
text content block.

For shell/CLI work the same contract applies to agent-visible summaries:
status → one-line summary → next actions → artifacts (paths / SHAs).

## 3. Error recovery contract

For every error path, provide all three or the error is incomplete:

1. **Root cause hint** — the envelope `hint` field (e.g. 404 → "GET
   /business/api/library lists valid ids").
2. **Safe retry instruction** — `retryable: true` means re-invoking with a
   corrected input is safe; `false` means do not retry blindly (413 too-large,
   404 missing resource).
3. **Explicit stop condition** — stop after the fix attempt fails once; never
   loop on the same failing input.

Known environment trap: shell runners can truncate/mangle commands with nested
quotes or heredocs (exit 127). Safe retry = write the script to `/tmp`,
run `bash -lc /tmp/script.sh`, read outputs via file reads. Stop after one
retry and switch strategy.

## 4. Context budgeting

- Keep prompts minimal; load guidance on demand (this file, `AGENTS.md`).
- Prefer file paths over inlined content; read ranges, not whole files.
- Compact at phase boundaries (plan → implement → verify → ship), not at
  arbitrary token thresholds.
- Never inline secrets; reference `.env` / `server/data/freeapi.db` by path
  only.

## 5. Verification gate (definition of done)

An agent may declare completion only after ALL of:

1. `cd server && npx tsc --noEmit` exits 0;
2. `cd server && npx vitest run --pool=forks --fileParallelism=false` passes;
3. for shipped changes: commit exists on the writable remote and its SHA is
   reported back as an artifact.

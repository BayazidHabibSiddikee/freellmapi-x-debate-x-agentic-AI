# CLAUDE.md — agent guidance for this repository

FreeLLMAPI: Express 5 + TypeScript ESM monorepo (`shared`, `server`, `client`
npm workspaces) with a React/Vite client. The Business module adds an
AI-team layer with a hybrid BM25 + embedding RAG knowledge library.

## Commands

```bash
npm install                      # workspaces install (root)
npm run dev                      # server (:3001) + client concurrently
cd server && npx tsc --noEmit    # typecheck (CI gates on build = tsc)
cd server && npx vitest run --pool=forks --fileParallelism=false   # all tests
cd server && npx vitest run src/__tests__/services/rag.test.ts     # one file
npm run build                    # tsc + client build
```

CI (`.github/workflows/ci.yml`): install → `npm test` → `npm run build`.
Run both locally before declaring done.

## Conventions

- ESM everywhere: relative imports in `server/src` end with `.js`.
- Response envelope: use `sendOk` / `sendError` from `server/src/lib/envelope.ts`
  for Business/agent-facing routes (contract in `docs/agent-harness.md`).
- Tests live in `server/src/__tests__/**`, run under vitest, globals enabled.
- Data directories: repo-root `data/` (characters, library, debate sessions);
  `server/data/` is local-only runtime state.

## Secrets — read before ANY commit

NEVER stage or commit:

- `server/data/` — contains `freeapi.db` (encrypted API keys)
- `decrypt.js`, `update_hermes.js` — contain a hardcoded AES-256 key
- `.env`, `*.db`, `*.db-wal`, `*.db-shm`, `pids/`, `logs/`

All are gitignored; verify with `git status --short` before committing and
confirm none of the above appear.

## Push targets

The workspace origin `tashfeenahmed/freellmapi` rejects pushes from the local
credential (403). The writable remote for shipped changes is
`BayazidHabibSiddikee/freellmapi-x-debate-x-agentic-AI` — check that repo's
`main` before pushing; it may already contain equivalent content.

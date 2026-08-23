# ❓ HELP — FreeLLMAPI × Debate × Agentic AI

Everything you need to run and use the platform. See **GOAL.md** for the "why".

---

## 1. Starting & stopping

```bash
./run.sh install   # one-time: npm deps + python venv
./run.sh start     # start everything
./run.sh status    # what's up/down
./run.sh stop      # stop everything
./run.sh restart
```

| Service | Port | What it serves |
|---|---|---|
| Express (FreeLLM API) | `3001` | LLM proxy, dashboard, playground, debate UI, knowledge hub |
| Debate server | `5050` | Character debate simulator (Python/FastAPI) |
| Hybrid RAG | `5080` | BM25 + embeddings search over your library |
| Agent tools | `5090` | Role-gated tools, judge, dispatch to claude/opencode |
| Console | `18443` | Next.js console incl. **/business** team surface |
| Telegram bridge | — | @kaggle_shot_bot relay (no port; long-polls) |

Logs live in `logs/` and are viewable in the Business page's **Logs** card.

---

## 2. The three main surfaces

### 🏢 Business team — http://localhost:18443/business

1. **Roles card** — assign characters to CTO / PM / Judge / Researcher /
   Engineer / Analyst. Multiple characters per role is fine (they take turns).
   Pin a **workspace** per role (must be under `~/`) — dispatched work happens there.
2. **Characters card** — browse/search all 38 characters, click one to assign it
   to any role.
3. **Settings card** — model, temperature, RAG depth, default dispatch agent,
   timeouts, whether dispatched agents may edit files.
4. **Working session** — set a topic, press **Speak** (or a specific role button).
5. **Judge → Dispatch** — distill the debate into a task spec, then execute each
   subtask via headless `claude -p` / `opencode run`.

> First time on the console you'll be sent through `?t=<token>` auth — that token
> lives in `~/.hermes/agentic-os/token`.

### 🎭 Debate simulator — http://localhost:3001/debate

- Pick characters, type a topic, chat turn-by-turn or use auto-play.
- **History panel**: click any past conversation to reload it; the trash icon deletes it.
- `/personal` for 1-on-1 roleplay, `/knowledge` to upload documents into hybrid RAG.

### 🤖 Telegram — add @kaggle_shot_bot to a group

```
/team            roles & members
/topic <text>    set the working topic
/ask <text>      next member speaks
/speak CTO       force a role to answer
/debate 5        n automatic turns
/judge           task-spec summary
/status          service health
/reset           clear this chat's session
```

Note: the bot currently runs with Telegram privacy mode ON — it sees slash
commands only. Disable via BotFather `/setprivacy` if you want plain messages too.

---

## 3. Feeding the knowledge base

Any of these end up in the same hybrid index (BM25 + MiniLM embeddings):

- Business page → **Team tools** → `download_books` (Researcher role downloads
  books/PDFs from the web and auto-ingests them)
- http://localhost:3001/knowledge → drag-and-drop upload (PDF/DOCX/TXT/MD)
- Drop files directly into `services/debate/doc/`, then restart RAG or POST to
  `localhost:5080/upload/doc`

Search it: `POST localhost:5080/search {"query": "...", "mode": "hybrid"}`.

---

## 4. Configuration cheat-sheet

| What | Where |
|---|---|
| Roles / members / workspaces | `config/business/roles.json` (UI: Roles card) |
| Model, temp, RAG-k, timeouts, file-write permission | `config/business/settings.json` (UI: Settings card) |
| Custom characters | `config/business/custom_characters.json` |
| Base character roster | `services/debate/characters.json` |
| Telegram bot token | `.env` → `TELEGRAM_BOT_TOKEN` (gitignored) |
| FreeLLM provider keys | Dashboard → Keys page (stored encrypted) |
| Let dispatched agents write files | Settings → *Allow file writes*, or env `CLAUDE_FLAGS=--permission-mode acceptEdits` |

Environment overrides: `RAG_SERVER_URL`, `AGENT_TOOLS_URL`, `FREELM_API_BASE`,
`FREELM_MODEL`, `DISPATCH_TIMEOUT`, `CONSOLE_URL`.

---

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| Console asks for auth / 401s | Open via the launch URL with `?t=<token>` from `~/.hermes/agentic-os/token` |
| Debate history item won't load | Ensure Express was restarted after this fix (`./run.sh restart`) |
| `/api/business/chat` says "no character assigned" | Assign at least one member in the Roles card |
| Judge returns garbage JSON | Retry once; check `model` in Settings (`auto` routes well) |
| Dispatch fails "CLI not found" | Install `claude` / `opencode` CLIs and ensure they're on PATH |
| Dispatch can't write files | Enable file writes in Settings or set `CLAUDE_FLAGS` |
| Downloads find nothing | PDF sources are flaky; try more specific titles, or run Camoufox (`camofox-browser`) for the stealth-search cascade |
| RAG health shows `"hybrid": false` | `pip install rank-bm25` in `services/debate/venv` |
| Telegram silent | Check `logs/telegram.log`; verify token with `curl https://api.telegram.org/bot<TOKEN>/getMe` |

Still stuck? Check `logs/activity.jsonl` — every tool run, judge call, and
dispatch is journaled there.

---

## 6. Repo map

```
server/ client/     FreeLLM API proxy + dashboard (Express + React)
console/            Next.js console (Business, vault, skills, automations)
services/debate/    debate simulator + hybrid RAG server (Python)
services/agent/     tool registry, judge, dispatcher, activity log
services/telegram/  @kaggle_shot_bot bridge
tools/              pdf_downloader, stealth_browser, youtube_transcript, …
config/business/    roles, settings, custom characters, telegram sessions
data/               characters, debate sessions, exports
docs/               HTML surfaces served by Express (/debate /knowledge …)
logs/               all service logs + activity journal
GOAL.md             why this project exists
```

# SwordOffice — Help & Operations Manual

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

### 🏢 Where the team actually works — the three surfaces

| Surface | Identity | What happens there |
|---|---|---|
| **Business** (`:18443/business`) | **The workplace** | Roles, tool grants, projects, boardroom debates, judge→dispatch. Deliverables and decisions land here |
| **The Office** (`:18443/business/rooms`) | **1-on-1 rooms** | Private persistent chats with any of the ~46 people. Each person remembers past conversations (PostgreSQL) and those memories bleed into boardroom debates |
| **Debate** (`:3001/debate`) | **The arena** | Adversarial group roleplay with the original 18 characters; reputations form |

Memory architecture: one PostgreSQL database (`swordoffice-pg` Docker container,
schema `office`, SQLite auto-fallback) — `teams`, `rooms`, `messages`,
`persona_memory`. Memories are **directional**: what Ada knows about Kai is
stored separately from what Kai knows about Ada, and when a character is about
to speak in the boardroom, the system injects what they remember about the
teammates present. Personas are rows, not databases — 46 people, one backup.


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

## 5. Verified message flow

Every hop below is tested and working. All LLM traffic funnels through the
local FreeLLM proxy on :3001 — nothing talks to remote APIs directly.

```
 BROWSER / TELEGRAM
   │
   ├─ :3001/debate  ──► Express /debate/api/chat ──┐
   ├─ :3001/personal ─┘                            │
   ├─ :18443/business ──► console API ─────────────┤
   └─ telegram bot ─────► console API ─────────────┤
                                                   ▼
                                    FreeLLM proxy :3001/v1
                                     (16+ providers, auto-route)
                                                   ▼
                                        auto (FreeLLM proxy routes to your configured default)

 Grounding side (parallel):
   console/agent tools ──► RAG :5080 (BM25 + FAISS, RRF fusion)
   agent tools ──► tools/pdf_downloader etc. ──► ingest back into RAG
   judge/dispatcher ──► :3001/v1 + headless claude/opencode CLIs
```

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `[Error: Could not generate response - Connection error.]` on :5050 chat | The old default pointed at Ollama (:11434). Fixed — `services/debate/.env` now targets the local proxy. Ensure Express (:3001) is running, then restart debate: kill the process and re-run `./run.sh start` |
| Chat replies leak meta-text ("traits", "instructions") | Fixed by pinning `gemini-3.5-flash`. Override via `DEBATE_MODEL` env or Settings card |
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

## 7. What framework is used? (LangChain / LangGraph / LangSmith?)

| Library | Used? | Where |
|---|---|---|
| **LangChain** | ✅ Yes | `services/debate/` — `ChatOpenAI` for character turns, HuggingFace embeddings, FAISS vectorstore, text splitters |
| **rank-bm25 + faiss-cpu** | ✅ Yes | the hybrid retrieval itself (BM25 sparse + dense vectors fused via RRF) |
| **FastAPI** | ✅ Yes | debate (:5050), RAG (:5080), agent tools (:5090) servers |
| **Express / React / Next.js** | ✅ Yes | FreeLLM proxy+dashboard; agentic-os console incl. Business |
| **LangGraph** | ❌ No | Only the original Marin project used a LangGraph state machine; this monorepo uses a simpler direct call flow (route → prompt → proxy → persona) |
| **LangSmith** | ❌ No | Installed only as a transitive dependency of LangChain. No tracing key is set; if you ever export `LANGCHAIN_TRACING_V2=true` it would start uploading traces — don't unless you want that |

## 8. Repo map

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

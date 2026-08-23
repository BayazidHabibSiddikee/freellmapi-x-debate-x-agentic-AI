"""
services/telegram/bot.py — Telegram bridge for the Business AI team.

Lets you talk to your character team from any Telegram group through
@kaggle_shot_bot. The bot relays messages to the console's Business API,
which composes role prompts + character personas and injects hybrid-RAG
context — so the same team you debate with in /business answers here.

Commands (in the group):
  /team              — show roles and their assigned characters
  /topic <text>      — set the working-session topic
  /ask <text>        — next team member speaks on the topic (or asks fresh)
  /speak <Role>      — force a specific role to speak next (e.g. /speak CTO)
  /debate <n>        — n automatic round-robin turns on the topic
  /judge             — judge distills the discussion into a task spec
  /status            — health of rag / agent / express / console
  plain text         — treated as /ask when privacy mode allows it
  @kaggle_shot_bot … — mention also counts as /ask

Env:
  TELEGRAM_BOT_TOKEN   (required) bot token from BotFather
  TELEGRAM_CHAT_ID     optional allowlist — only this chat id is served
  CONSOLE_URL          default http://localhost:18443
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

MONOREPO_ROOT = Path(__file__).resolve().parents[2]
TOKEN_FILE = Path.home() / ".hermes" / "agentic-os" / "token"
SESSIONS_FILE = MONOREPO_ROOT / "config" / "business" / "telegram_sessions.json"
SETTINGS_FILE = MONOREPO_ROOT / "config" / "business" / "settings.json"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CONSOLE_URL = os.environ.get("CONSOLE_URL", "http://localhost:18443")
ALLOWED_CHATS = {
    int(x) for x in os.environ.get("TELEGRAM_CHAT_ID", "").replace(" ", "").split(",") if x
}

API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ── helpers ───────────────────────────────────────────────────────────────────

def console_token() -> str:
    return TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else ""


def console_get(path: str) -> Any:
    r = requests.get(
        f"{CONSOLE_URL}{path}",
        params={"t": console_token()},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def console_post(path: str, body: Dict[str, Any], timeout: int = 180) -> Any:
    r = requests.post(
        f"{CONSOLE_URL}{path}",
        params={"t": console_token()},
        json=body,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def load_sessions() -> Dict[str, Any]:
    try:
        return json.loads(SESSIONS_FILE.read_text())
    except Exception:  # noqa: BLE001
        return {}


def save_sessions(sessions: Dict[str, Any]) -> None:
    SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSIONS_FILE.write_text(json.dumps(sessions, indent=2))


def tg(method: str, **payload: Any) -> Optional[Dict[str, Any]]:
    """Telegram API call; never raises."""
    try:
        r = requests.post(f"{API}/{method}", json=payload, timeout=35)
        data = r.json()
        if not data.get("ok"):
            print(f"[tg] {method} failed: {data}")
            return None
        return data["result"]
    except Exception as e:  # noqa: BLE001
        print(f"[tg] {method} error: {e}")
        return None


def send(chat_id: int, text: str, parse: str = "HTML") -> None:
    # Telegram hard limit 4096 chars
    for i in range(0, len(text), 4000):
        tg("sendMessage", chat_id=chat_id, text=text[i : i + 4000], parse_mode=parse)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── command handlers ──────────────────────────────────────────────────────────

def cmd_team(chat_id: int) -> str:
    roster = console_get("/api/business/roster")
    chars = {c["id"]: c["name"] for c in roster["characters"]}
    lines = ["<b>Your team</b>"]
    for role, cfg in roster["roles"].items():
        members = [esc(chars.get(m, m)) for m in cfg.get("members", [])]
        ws = cfg.get("workspace")
        line = f"\n<b>{role}</b>: {', '.join(members) if members else '—'}"
        if ws:
            line += f"\n  📁 <code>{esc(ws)}</code>"
        lines.append(line)
    return "\n".join(lines)


def get_history(state: Dict[str, Any]) -> List[Dict[str, str]]:
    return state.setdefault("history", [])


def speak_turn(chat_id: int, state: Dict[str, Any], role: Optional[str] = None) -> str:
    topic = state.get("topic", "")
    if not topic:
        return "No topic yet. Set one first:\n<code>/topic your project question</code>"
    data = console_post(
        "/api/business/chat",
        {"topic": topic, "history": get_history(state), "role": role},
    )
    speaker = esc(data.get("speaker", "?"))
    rle = data.get("role", "")
    badge = f" [{rle}]" if rle else ""
    rag = "\n🔗 grounded in your knowledge base" if data.get("used_rag") else ""
    text = esc(data.get("text", ""))
    get_history(state).append({"speaker": data.get("speaker", "?"), "text": data.get("text", "")})
    state["rr_counter"] = state.get("rr_counter", 0) + 1
    return f"<b>{speaker}</b>{badge}\n{text}{rag}"


def cmd_debate(chat_id: int, state: Dict[str, Any], n: int) -> str:
    n = max(1, min(n, 8))
    outs = []
    roster_roles = list(console_get("/api/business/roster")["roles"].items())
    active = [(r, cfg) for r, cfg in roster_roles if cfg.get("members")]
    for _ in range(n):
        for role, cfg in active:
            outs.append(speak_turn(chat_id, state, role))
            save_sessions(SESSIONS_STATE)  # persist as we go
    return "\n\n———\n\n".join(outs)


def cmd_judge(chat_id: int, state: Dict[str, Any]) -> str:
    topic = state.get("topic", "")
    if not topic or not get_history(state):
        return "Nothing to judge yet. Use /topic then /ask or /debate."
    data = console_post(
        "/api/business/judge",
        {"topic": topic, "history": get_history(state)},
        timeout=300,
    )
    if not data.get("ok"):
        return f"Judge failed: {esc(str(data.get('error', 'unknown')))}"
    spec = data["spec"]
    lines = [f"<b>⚖️ Goal:</b> {esc(spec.get('goal', ''))}"]
    for d in spec.get("decisions", []):
        lines.append(f"• {esc(d)}")
    lines.append("\n<b>Subtasks</b>")
    for t in spec.get("subtasks", []):
        agent_icon = "🤖" if t.get("agent") == "claude" else "⚙️"
        lines.append(f"{agent_icon} <b>{esc(t['id'])}</b> {esc(t['title'])}")
    lines.append("\nDispatch from the Business console → " + f"{CONSOLE_URL}/business")
    return "\n".join(lines)


def cmd_status(chat_id: int) -> str:
    checks = [
        ("FreeLLM :3001", "http://localhost:3001/api/health"),
        ("Debate :5050", "http://localhost:5050/api/health"),
        ("RAG :5080", "http://localhost:5080/health"),
        ("Agent :5090", "http://localhost:5090/health"),
    ]
    lines = []
    for name, url in checks:
        try:
            ok = requests.get(url, timeout=5).ok
        except Exception:  # noqa: BLE001
            ok = False
        lines.append(f"{'✅' if ok else '❌'} {name}")
    return "\n".join(lines)


HELP = (
    "<b>Gemini — Business Team Bridge</b>\n"
    "/team — show roles &amp; characters\n"
    "/topic &lt;text&gt; — set the working topic\n"
    "/ask &lt;text&gt; — team speaks (&lt;text&gt; becomes the topic if none set)\n"
    "/speak &lt;Role&gt; — force a role to speak (CTO, PM, Judge, Researcher, Engineer, Analyst)\n"
    "/debate &lt;n&gt; — n automatic round-robin turns\n"
    "/judge — distill discussion into a task spec\n"
    "/status — service health\n"
    "/reset — clear this chat's session"
)

SESSIONS_STATE: Dict[str, Dict[str, Any]] = {}


# ── update handling ───────────────────────────────────────────────────────────

def handle_message(msg: Dict[str, Any]) -> None:
    chat_id = msg["chat"]["id"]
    if ALLOWED_CHATS and chat_id not in ALLOWED_CHATS:
        return
    text = (msg.get("text") or "").strip()
    if not text:
        return

    state = SESSIONS_STATE.setdefault(str(chat_id), load_sessions().get(str(chat_id), {}))

    if text.startswith("/start") or text.startswith("/help"):
        send(chat_id, HELP)
        return
    if text.startswith("/reset"):
        SESSIONS_STATE.pop(str(chat_id), None)
        sessions = load_sessions()
        sessions.pop(str(chat_id), None)
        save_sessions(sessions)
        send(chat_id, "Session cleared.")
        return

    try:
        if text.startswith("/team"):
            send(chat_id, cmd_team(chat_id))

        elif text.startswith("/topic"):
            state["topic"] = text.split(" ", 1)[1].strip() if " " in text else ""
            state["history"] = []
            send(chat_id, f"📌 Topic set:\n{esc(state['topic'])}")

        elif text.startswith("/speak"):
            arg = text.split(" ", 1)[1].strip().upper() if " " in text else ""
            valid = {"CTO", "PM", "JUDGE", "RESEARCHER", "ENGINEER", "ANALYST"}
            if arg not in valid:
                send(chat_id, f"Usage: /speak {'|'.join(sorted(valid))}")
                return
            send(chat_id, speak_turn(chat_id, state, arg.capitalize()))

        elif text.startswith("/debate"):
            arg = text.split(" ", 1)[1].strip() if " " in text else "3"
            send(chat_id, cmd_debate(chat_id, state, int(arg) if arg.isdigit() else 3))

        elif text.startswith("/judge"):
            send(chat_id, cmd_judge(chat_id, state))

        elif text.startswith("/status"):
            send(chat_id, cmd_status(chat_id))

        elif text.startswith("/ask"):
            body = text.split(" ", 1)[1].strip() if " " in text else ""
            if body and not state.get("topic"):
                state["topic"] = body
                state["history"] = []
            elif body:
                get_history(state).append({"speaker": "You", "text": body})
            send(chat_id, speak_turn(chat_id, state))

        else:
            # plain text or @mention → treat as ask
            if not state.get("topic"):
                state["topic"] = text
                state["history"] = []
                send(chat_id, f"📌 Topic set:\n{esc(text)}")
            else:
                get_history(state).append({"speaker": "You", "text": text})
            send(chat_id, speak_turn(chat_id, state))

    except Exception as e:  # noqa: BLE001 — report failures into the chat
        send(chat_id, f"⚠️ {esc(str(e)[:300])}")

    # persist
    sessions = load_sessions()
    sessions[str(chat_id)] = state
    save_sessions(sessions)


def poll_loop() -> None:
    offset = 0
    print(f"[tg] polling as bot… allowed chats: {ALLOWED_CHATS or 'any'}")
    while True:
        try:
            r = requests.get(
                f"{API}/getUpdates",
                params={"offset": offset, "timeout": 25},
                timeout=35,
            )
            data = r.json()
            if not data.get("ok"):
                print(f"[tg] getUpdates failed: {data}")
                time.sleep(5)
                continue
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message")
                if msg:
                    try:
                        handle_message(msg)
                    except Exception as e:  # noqa: BLE001
                        print(f"[tg] handler error: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"[tg] poll error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN (see .env)")
    me = tg("getMe")
    if not me:
        raise SystemExit("Telegram API unreachable / bad token")
    print(f"[tg] connected as @{me['username']}")
    poll_loop()

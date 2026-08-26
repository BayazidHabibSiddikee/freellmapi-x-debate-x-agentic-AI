"""
services/telegram/bot.py — Multi-bot Telegram bridge for the Business AI team.

Loads per-bot configs from config/business/telegram_bots.json. Each bot runs its
own polling loop in a daemon thread with independent sessions. Legacy single-bot
mode still works when TELEGRAM_BOT_TOKEN is set but no config exists.

Commands (in any bot group):
  /team              — show roles and their assigned characters
  /topic <text>      — set the working-session topic
  /ask <text>        — next team member speaks on the topic (or asks fresh)
  /speak <Role>      — force a specific role to speak next (e.g. /speak CTO)
  /debate <n>        — n automatic round-robin turns on the topic
  /judge             — judge distills the discussion into a task spec
  /status            — health of rag / agent / express / console
  plain text         — treated as /ask when privacy mode allows it
  @bot … — mention also counts as /ask

Usage:
  python bot.py --poll            # run all active bots in daemon threads
  python bot.py --bot-name Alpha  # run just "Alpha"
  python bot.py --poll --once     # dry-run: fetch one batch from each bot then exit

Env (legacy single-bot mode only):
  TELEGRAM_BOT_TOKEN   bot token from BotFather
  TELEGRAM_CHAT_ID     optional allowlist — only these chat ids are served
  CONSOLE_URL          default http://localhost:18443
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from threading import Thread
from typing import Any, Dict, List, Optional

import requests

MONOREPO_ROOT = Path(__file__).resolve().parents[2]
TOKEN_FILE = Path.home() / ".hermes" / "agentic-os" / "token"
SESSIONS_FILE = MONOREPO_ROOT / "config" / "business" / "telegram_sessions.json"
SETTINGS_FILE = MONOREPO_ROOT / "config" / "business" / "settings.json"

# Legacy env-var fallback (single-bot only)
LEGACY_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CONSOLE_URL = os.environ.get(
    "CONSOLE_PUBLIC_URL",
    os.environ.get("CONSOLE_URL", "http://localhost:18443"),
)
LEGACY_ALLOWED = {
    int(x)
    for x in os.environ.get("TELEGRAM_CHAT_ID", "").replace(" ", "").split(",")
    if x
}


# ── Config types ───────────────────────────────────────────────────────────────

def _load_settings() -> Dict[str, Any]:
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except Exception:  # noqa: BLE001
        return {}


def load_bots_config() -> List[Dict[str, Any]]:
    """Return configured bots from settings.telegram_bots (skips inactive).

    Returns empty list when no telegram_bots are configured — caller falls
    back to LEGACY_TOKEN if present.
    """
    settings = _load_settings()
    bots: List[Dict[str, Any]] = settings.get("telegram_bots", []) or []
    return [b for b in bots if b.get("active", True)]


def make_bot(b: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a config dict into the shape the handler expects."""
    return {
        "id": b.get("id", "default"),
        "name": b.get("name", b.get("id", "default")),
        "token": b["bot_token"],
        "allowed_chat_ids": set(
            int(x)
            for x in (b.get("allowed_chat_ids") or [])
            if str(x).strip()
        ),
    }


def bot_session_file(bot_name: str) -> Path:
    """Per-bot session file lives alongside the singleton sessions file."""
    safe = "".join(c if c.isalnum() else "_" for c in bot_name)
    return SESSIONS_FILE.parent / f"telegram_sessions_{safe}.json"


# ── Bot instance helpers ───────────────────────────────────────────────────────

class BotInstance:
    """Encapsulates everything a single bot needs: token, API base, session state."""

    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.name = cfg["name"]
        self.token = cfg["token"]
        self.allowed = cfg["allowed_chat_ids"]  # set of ints or empty → allow all
        self.api = f"https://api.telegram.org/bot{self.token}"
        self.session_file = bot_session_file(self.name)

    def tg(self, method: str, **payload: Any) -> Optional[Dict[str, Any]]:
        """Telegram API call; never raises — prints instead."""
        try:
            r = requests.post(f"{self.api}/{method}", json=payload, timeout=35)
            data = r.json()
            if not data.get("ok"):
                print(f"[tg:{self.name}] {method} failed: {data}")
                return None
            return data["result"]
        except Exception as e:  # noqa: BLE001
            print(f"[tg:{self.name}] {method} error: {e}")
            return None

    def send(self, chat_id: int, text: str, parse: str = "HTML") -> None:
        for i in range(0, len(text), 4000):
            self.tg("sendMessage", chat_id=chat_id, text=text[i : i + 4000],
                    parse_mode=parse)

    def get_me(self) -> Optional[Dict[str, Any]]:
        return self.tg("getMe")

    def esc(self, s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # ── Console bridge ────────────────────────────────────────────────────────

    def console_token(self) -> str:
        return TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else ""

    def console_get(self, path: str) -> Any:
        r = requests.get(
            f"{CONSOLE_URL}{path}",
            params={"t": self.console_token()},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def console_post(self, path: str, body: Dict[str, Any], timeout: int = 180) -> Any:
        r = requests.post(
            f"{CONSOLE_URL}{path}",
            params={"t": self.console_token()},
            json=body,
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()

    # ── Per-chat sessions ──────────────────────────────────────────────────────

    def load_sessions(self) -> Dict[str, Any]:
        try:
            return json.loads(self.session_file.read_text())
        except Exception:  # noqa: BLE001
            return {}

    def save_sessions(self, sessions: Dict[str, Any]) -> None:
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        self.session_file.write_text(json.dumps(sessions, indent=2))

    def get_state(self, chat_id: str, sessions: Dict[str, Any]) -> Dict[str, Any]:
        return sessions.setdefault(chat_id, sessions.get(chat_id, {}))

    def save_state(self, chat_id: str, state: Dict[str, Any],
                   sessions: Dict[str, Any]) -> None:
        sessions[chat_id] = state
        self.save_sessions(sessions)

    # ── Command handlers ────────────────────────────────────────────────────────

    HELP = (
        "<b>Business Team Bridge</b>\n"
        "/team — show roles &amp; characters\n"
        "/topic &lt;text&gt; — set the working topic\n"
        "/ask &lt;text&gt; — team speaks (&lt;text&gt; becomes topic if none set)\n"
        "/speak &lt;Role&gt; — force a role (CTO, PM, Judge, Researcher, Engineer, Analyst)\n"
        "/debate &lt;n&gt; — n automatic round-robin turns\n"
        "/judge — distill discussion into a task spec\n"
        "/status — service health\n"
        "/reset — clear this chat's session"
    )

    def cmd_team(self, chat_id: int) -> str:
        roster = self.console_get("/api/business/roster")
        chars = {c["id"]: c["name"] for c in roster["characters"]}
        lines = ["<b>Your team</b>"]
        for role, cfg in roster["roles"].items():
            members = [self.esc(chars.get(m, m)) for m in cfg.get("members", [])]
            ws = cfg.get("workspace")
            line = f"\n<b>{role}</b>: {', '.join(members) if members else '—'}"
            if ws:
                line += f"\n  📁 <code>{self.esc(ws)}</code>"
            lines.append(line)
        return "\n".join(lines)

    def speak_turn(self, chat_id: int, state: Dict[str, Any],
                   role: Optional[str] = None) -> str:
        topic = state.get("topic", "")
        if not topic:
            return "No topic yet. Set one first:\n<code>/topic your project question</code>"
        history: List[Dict[str, str]] = state.setdefault("history", [])
        data = self.console_post(
            "/api/business/chat",
            {"topic": topic, "history": history, "role": role},
        )
        speaker = self.esc(data.get("speaker", "?"))
        rle = data.get("role", "")
        badge = f" [{rle}]" if rle else ""
        rag = "\n🔗 grounded in your knowledge base" if data.get("used_rag") else ""
        text = self.esc(data.get("text", ""))
        history.append({"speaker": data.get("speaker", "?"), "text": data.get("text", "")})
        state["rr_counter"] = state.get("rr_counter", 0) + 1
        topic_slug = topic[:50].replace(" ", "-").replace("/", "-")
        boardroom_url = f"{CONSOLE_URL}/business?topic={topic_slug}"
        return (
            f"<b>{speaker}</b>{badge}\n{text}{rag}\n\n"
            f'<a href="{boardroom_url}">🖥 Continue in Boardroom</a>'
        )

    def cmd_debate(self, chat_id: int, state: Dict[str, Any], n: int) -> str:
        n = max(1, min(n, 8))
        outs = []
        roster_roles = list(self.console_get("/api/business/roster")["roles"].items())
        active = [(r, cfg) for r, cfg in roster_roles if cfg.get("members")]
        for _ in range(n):
            for role, cfg in active:
                outs.append(self.speak_turn(chat_id, state, role))
                sessions = self.load_sessions()
                self.save_state(str(chat_id), state, sessions)
        return "\n\n———\n\n".join(outs)

    def cmd_judge(self, chat_id: int, state: Dict[str, Any]) -> str:
        topic = state.get("topic", "")
        if not topic or not state.get("history"):
            return "Nothing to judge yet. Use /topic then /ask or /debate."
        data = self.console_post(
            "/api/business/judge",
            {"topic": topic, "history": state["history"]},
            timeout=300,
        )
        if not data.get("ok"):
            return f"Judge failed: {self.esc(str(data.get('error', 'unknown')))}"
        spec = data["spec"]
        lines = [f"<b>⚖️ Goal:</b> {self.esc(spec.get('goal', ''))}"]
        for d in spec.get("decisions", []):
            lines.append(f"• {self.esc(d)}")
        lines.append("\n<b>Subtasks</b>")
        for t in spec.get("subtasks", []):
            icon = "🤖" if t.get("agent") == "claude" else "⚙️"
            lines.append(f"{icon} <b>{self.esc(t['id'])}</b> {self.esc(t['title'])}")
        boardroom_topic = topic.replace(" ", "-")[:50]
        lines.append(
            "\nDispatch from the Business console → "
            f"{CONSOLE_URL}/business?topic={boardroom_topic}"
        )
        return "\n".join(lines)

    def cmd_status(self, chat_id: int) -> str:
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

    # ── Single-message dispatch ────────────────────────────────────────────────

    def handle_message(self, msg: Dict[str, Any]) -> None:
        chat_id = int(msg["chat"]["id"])

        # Allowlist gate
        if self.allowed and chat_id not in self.allowed:
            return

        text = (msg.get("text") or "").strip()
        if not text:
            return

        sessions = self.load_sessions()
        chat_key = str(chat_id)
        state = self.get_state(chat_key, sessions)

        if text.startswith("/start") or text.startswith("/help"):
            self.send(chat_id, self.HELP)
            return

        if text.startswith("/reset"):
            sessions.pop(chat_key, None)
            self.save_sessions(sessions)
            self.send(chat_id, "Session cleared.")
            return

        try:
            if text.startswith("/team"):
                self.send(chat_id, self.cmd_team(chat_id))

            elif text.startswith("/topic"):
                state["topic"] = text.split(" ", 1)[1].strip() if " " in text else ""
                state["history"] = []
                self.save_state(chat_key, state, sessions)
                self.send(chat_id, f"📌 Topic set:\n{self.esc(state['topic'])}")

            elif text.startswith("/speak"):
                arg = text.split(" ", 1)[1].strip().upper() if " " in text else ""
                valid = {"CTO", "PM", "JUDGE", "RESEARCHER", "ENGINEER", "ANALYST"}
                if arg not in valid:
                    self.send(chat_id, f"Usage: /speak {'|'.join(sorted(valid))}")
                    return
                self.send(chat_id, self.speak_turn(chat_id, state, arg.capitalize()))

            elif text.startswith("/debate"):
                arg = text.split(" ", 1)[1].strip() if " " in text else "3"
                self.send(chat_id,
                          self.cmd_debate(chat_id, state, int(arg) if arg.isdigit() else 3))

            elif text.startswith("/judge"):
                self.send(chat_id, self.cmd_judge(chat_id, state))

            elif text.startswith("/status"):
                self.send(chat_id, self.cmd_status(chat_id))

            elif text.startswith("/ask"):
                body = text.split(" ", 1)[1].strip() if " " in text else ""
                if body and not state.get("topic"):
                    state["topic"] = body
                    state["history"] = []
                elif body:
                    state.setdefault("history", []).append(
                        {"speaker": "You", "text": body})
                self.save_state(chat_key, state, sessions)
                self.send(chat_id, self.speak_turn(chat_id, state))

            else:
                # plain text or @mention → treat as ask
                if not state.get("topic"):
                    state["topic"] = text
                    state["history"] = []
                    self.send(chat_id, f"📌 Topic set:\n{self.esc(text)}")
                else:
                    state.setdefault("history", []).append(
                        {"speaker": "You", "text": text})
                self.save_state(chat_key, state, sessions)
                self.send(chat_id, self.speak_turn(chat_id, state))

        except Exception as e:  # noqa: BLE001 — report failures into the chat
            self.send(chat_id, f"⚠️ {self.esc(str(e)[:300])}")

        self.save_state(chat_key, state, sessions)


# ── Polling ─────────────────────────────────────────────────────────────────────

def poll_once(bot: BotInstance, offset: int = 0) -> int:
    """Fetch one batch of updates and handle them. Returns new offset."""
    try:
        r = requests.get(
            f"{bot.api}/getUpdates",
            params={"offset": offset, "timeout": 25},
            timeout=35,
        )
        data = r.json()
        if not data.get("ok"):
            print(f"[tg:{bot.name}] getUpdates failed: {data}")
            return offset
        for upd in data.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or upd.get("edited_message")
            if msg:
                try:
                    bot.handle_message(msg)
                except Exception as e:  # noqa: BLE001
                    print(f"[tg:{bot.name}] handler error: {e}")
    except Exception as e:  # noqa: BLE001
        print(f"[tg:{bot.name}] poll error: {e}")
    return offset


def poll_loop(bot: BotInstance) -> None:
    offset = 0
    print(f"[tg:{bot.name}] polling …")
    while True:
        offset = poll_once(bot, offset)
        time.sleep(1)


def run_single(bot: BotInstance, once: bool = False) -> None:
    """Run one bot: start a persistent poll or one shot depending on `once`."""
    me = bot.get_me()
    if not me:
        print(f"[tg:{bot.name}] unreachable or bad token ({bot.name})")
        return
    print(f"[tg:{bot.name}] connected as @{me['username']}")
    if once:
        poll_once(bot)
        return
    poll_loop(bot)


def run_all(bots: List[BotInstance], once: bool = False) -> None:
    """Start N bots in daemon threads (or one-shot)."""
    if not bots:
        print("[tg] no active bots configured — nothing to run")
        return
    threads: List[Thread] = []
    for bot in bots:
        t = Thread(target=run_single, args=(bot, once), daemon=True,
                   name=f"tg-{bot.name}")
        t.start()
        threads.append(t)
    print(f"[tg] started {len(threads)} bot(s): {', '.join(b.name for b in bots)}")
    if once:
        # Give threads time to drain, then exit
        time.sleep(2)
        return
    for t in threads:
        t.join()


# ── Legacy single-bot fallback ────────────────────────────────────────────────

def _legacy_run() -> None:
    """Backward-compatible single-bot mode when no telegram_bots config exists."""
    if not LEGACY_TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN (see .env)")
    api = f"https://api.telegram.org/bot{LEGACY_TOKEN}"
    me = requests.post(f"{api}/getMe", timeout=15).json()
    if not me.get("ok"):
        raise SystemExit("Telegram API unreachable / bad token")
    print(f"[tg:legacy] connected as @{me['result']['username']}")
    print("[tg:legacy] LEGACY MODE — configure telegram_bots in settings.json to use multi-bot")

    bot = BotInstance({
        "name": "legacy",
        "token": LEGACY_TOKEN,
        "allowed_chat_ids": LEGACY_ALLOWED,
    })
    poll_loop(bot)


# ── Entry point ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Telegram bot for the Business AI team")
    ap.add_argument("--poll", action="store_true", help="Start polling loop(s)")
    ap.add_argument("--once", action="store_true",
                    help="Fetch one batch then exit (no persistent loop)")
    ap.add_argument("--bot-name", default=None,
                    help="Run only this named bot (matches id field in config)")
    args = ap.parse_args()

    bots = load_bots_config()

    if not bots and not LEGACY_TOKEN:
        # No config at all — user may just be importing; nothing fatal here.
        sys.exit(0)

    if not bots:
        # Fallback to legacy env-based single bot
        if args.bot_name:
            print("[tg] --bot-name ignored in legacy mode")
        _legacy_run()
        sys.exit(0)

    filtered: List[BotInstance] = []
    for raw in bots:
        cfg = make_bot(raw)
        bot = BotInstance(cfg)
        if args.bot_name and bot.name != args.bot_name:
            continue
        filtered.append(bot)

    if not filtered:
        names = [b.get("id", "?") for b in bots]
        print(f"[tg] no bot matches '{args.bot_name}' — available: {names}")
        sys.exit(1)

    run_all(filtered, once=args.once)

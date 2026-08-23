#!/bin/bash
# FreeLLMAPI × Debate × Agentic AI - Unified Startup Script (monorepo)
# Usage: ./run.sh [start|stop|restart|status|install]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PID_DIR="$SCRIPT_DIR/pids"

mkdir -p "$LOG_DIR" "$PID_DIR"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

port_up() { lsof -i ":$1" >/dev/null 2>&1; }

wait_http() { # url tries
    for _ in $(seq 1 "${2:-15}"); do
        curl -s "$1" >/dev/null 2>&1 && return 0
        sleep 1
    done
    return 1
}

ensure_node_deps() {
    local dir="$1"
    if [ ! -d "$dir/node_modules" ]; then
        echo "Installing npm deps in $dir ..."
        (cd "$dir" && npm install --no-audit --no-fund >> "$LOG_DIR/npm-install.log" 2>&1)
    fi
}

ensure_venv() {
    local dir="$1" req="$2"
    if [ ! -f "$dir/venv/bin/python" ]; then
        echo "Creating Python venv in $dir ..."
        python3 -m venv "$dir/venv"
        "$dir/venv/bin/pip" install -q --upgrade pip
    fi
    if [ -n "$req" ] && ! "$dir/venv/bin/pip" show rank_bm25 >/dev/null 2>&1; then
        echo "Installing Python deps from $req ..."
        "$dir/venv/bin/pip" install -q -r "$dir/$req" >> "$LOG_DIR/pip-install.log" 2>&1
    fi
}

start_express() {  # FreeLLM API proxy + debate/business routes (:3001)
    if port_up 3001; then echo -e "${GREEN}✓ Express Server (:3001) already running${NC}"; return 0; fi
    ensure_node_deps "$SCRIPT_DIR"
    echo "Starting Express Server (:3001)..."
    cd "$SCRIPT_DIR"
    nohup npx tsx server/src/index.ts > "$LOG_DIR/freellmapi.log" 2>&1 &
    echo $! > "$PID_DIR/freellmapi.pid"
    wait_http http://localhost:3001/api/health && \
        echo -e "${GREEN}✓ Express Server running on :3001${NC}" || \
        { echo -e "${RED}✗ Failed to start Express Server${NC}"; return 1; }
}

start_vite() {  # optional dev dashboard (:5174)
    if port_up 5174; then echo -e "${GREEN}✓ Vite Dashboard (:5174) already running${NC}"; return 0; fi
    ensure_node_deps "$SCRIPT_DIR/client" 2>/dev/null || true
    echo "Starting Vite Dashboard (:5174, optional)..."
    cd "$SCRIPT_DIR"
    nohup npx vite --config client/vite.config.ts --port 5174 --host 0.0.0.0 > "$LOG_DIR/vite.log" 2>&1 &
    echo $! > "$PID_DIR/vite.pid"
    sleep 3
}

start_debate() {  # debate simulator (:5050)
    if port_up 5050; then echo -e "${GREEN}✓ Debate Server (:5050) already running${NC}"; return 0; fi
    ensure_venv "$SCRIPT_DIR/services/debate" "requirements-debate.txt"
    echo "Starting Debate Server (:5050)..."
    cd "$SCRIPT_DIR/services/debate"
    nohup ./venv/bin/python app.py > "$LOG_DIR/debate.log" 2>&1 &
    echo $! > "$PID_DIR/debate.pid"
    wait_http http://localhost:5050/api/health && \
        echo -e "${GREEN}✓ Debate Server running on :5050${NC}" || \
        { echo -e "${RED}✗ Failed to start Debate Server${NC}"; return 1; }
}

start_rag() {  # hybrid RAG server (:5080)
    if port_up 5080; then echo -e "${GREEN}✓ RAG Server (:5080) already running${NC}"; return 0; fi
    ensure_venv "$SCRIPT_DIR/services/debate" "requirements-rag.txt"
    echo "Starting Hybrid RAG Server (:5080)..."
    cd "$SCRIPT_DIR/services/debate"
    nohup ./venv/bin/python rag_server.py --port 5080 > "$LOG_DIR/rag.log" 2>&1 &
    echo $! > "$PID_DIR/rag.pid"
    wait_http http://localhost:5080/health && \
        echo -e "${GREEN}✓ RAG Server running on :5080${NC}" || \
        { echo -e "${RED}✗ Failed to start RAG Server${NC}"; return 1; }
}

start_agent() {  # business agent tools (:5090)
    if port_up 5090; then echo -e "${GREEN}✓ Agent Tools (:5090) already running${NC}"; return 0; fi
    ensure_venv "$SCRIPT_DIR/services/debate" "requirements-rag.txt"
    echo "Starting Agent Tools Server (:5090)..."
    cd "$SCRIPT_DIR/services/agent"
    nohup ../debate/venv/bin/python server.py --port 5090 > "$LOG_DIR/agent.log" 2>&1 &
    echo $! > "$PID_DIR/agent.pid"
    wait_http http://localhost:5090/health && \
        echo -e "${GREEN}✓ Agent Tools running on :5090${NC}" || \
        { echo -e "${RED}✗ Failed to start Agent Tools${NC}"; return 1; }
}

start_console() {  # agentic-os Next.js console (:18443)
    if port_up 18443; then echo -e "${GREEN}✓ Console (:18443) already running${NC}"; return 0; fi
    ensure_node_deps "$SCRIPT_DIR/console"
    echo "Starting Console (:18443)..."
    cd "$SCRIPT_DIR/console"
    nohup npm run dev > "$LOG_DIR/console.log" 2>&1 &
    echo $! > "$PID_DIR/console.pid"
    wait_http http://localhost:18443/ 20 && \
        echo -e "${GREEN}✓ Console running on http://localhost:18443${NC}" || \
        { echo -e "${RED}✗ Failed to start Console${NC}"; return 1; }
}

stop_all() {
    echo "Stopping all services..."
    for pidfile in "$PID_DIR"/*.pid; do
        [ -f "$pidfile" ] && kill "$(cat "$pidfile")" 2>/dev/null || true
    done
    pkill -f "tsx.*server/src/index.ts" 2>/dev/null || true
    pkill -f "vite.*client/vite.config" 2>/dev/null || true
    pkill -f "services/debate/app.py" 2>/dev/null || true
    pkill -f "rag_server.py --port 5080" 2>/dev/null || true
    pkill -f "server.py --port 5090" 2>/dev/null || true
    pkill -f "next dev -H 127.0.0.1 -p 18443" 2>/dev/null || true
    rm -f "$PID_DIR"/*.pid
    echo -e "${GREEN}✓ All services stopped${NC}"
}

show_status() {
    echo ""
    echo "=========================================="
    echo "     FreeLLMAPI × Debate × Agentic AI"
    echo "=========================================="
    check() {
        local name="$1" url="$2"
        if curl -s "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} $name"
        else
            echo -e "${RED}✗${NC} $name"
        fi
    }
    check "Express Server   :3001  http://localhost:3001/"          http://localhost:3001/api/health
    check "Debate Server    :5050  http://localhost:5050/chat"      http://localhost:5050/api/health
    check "Hybrid RAG       :5080  http://localhost:5080/health"    http://localhost:5080/health
    check "Agent Tools      :5090  http://localhost:5090/health"    http://localhost:5090/health
    check "Console          :18443 http://localhost:18443/"         http://localhost:18443/
    if port_up 5174; then
        echo -e "${YELLOW}⚠${NC} Vite Dashboard   :5174 (optional, running)"
    fi
    echo ""
    echo "  Business section: http://localhost:18443/business"
    echo "=========================================="
    echo ""
}

case "${1:-start}" in
    start)
        start_express
        start_rag
        start_debate
        start_agent
        start_console
        show_status
        ;;
    stop)    stop_all ;;
    restart) stop_all; sleep 2; "$0" start ;;
    status)  show_status ;;
    install)
        ensure_node_deps "$SCRIPT_DIR"
        ensure_node_deps "$SCRIPT_DIR/client"
        ensure_node_deps "$SCRIPT_DIR/console"
        ensure_venv "$SCRIPT_DIR/services/debate" "requirements-debate.txt"
        echo -e "${GREEN}✓ All dependencies installed${NC}"
        ;;
    *) echo "Usage: $0 {start|stop|restart|status|install}"; exit 1 ;;
esac

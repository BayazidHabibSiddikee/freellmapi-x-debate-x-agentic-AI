# syntax=docker/dockerfile:1.7
# Agent sandbox — a private machine for AI team members to work in.
#
# Design: inside this container the agent is ROOT and needs nobody's approval.
# It can install packages, write anywhere under /workspace, run builds/tests,
# and use network. Safety comes from ISOLATION (container boundary + the
# ./agent-workspace volume being the only host path mounted), not from
# permission prompts — exactly the "work freely" model marin uses for trusted
# roles, but hardened by default through the container edge.
FROM node:20-bookworm-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
       python3 python3-pip python3-venv \
       git curl wget jq ripgrep fd-find \
       build-essential ca-certificates procps \
  && rm -rf /var/lib/apt/lists/*

# Headless coding CLIs the team dispatches to (best-effort; available offline too).
RUN npm install -g --no-audit --no-fund \
      @anthropic-ai/claude-code \
      opencode-ai \
  || echo "[sandbox] one or more coding CLIs unavailable at build time — agents can still use node/python/git directly"

# psycopg so tools inside the sandbox can reach the SwordOffice Postgres.
RUN pip3 install --break-system-packages --quiet psycopg[binary] || pip3 install --quiet psycopg[binary] || true

WORKDIR /workspace
VOLUME ["/workspace"]

# The agent works as root IN HERE — full freedom inside, hard boundary outside.
ENV SWORDOFFICE_PG=postgresql://sword:swordoffice@postgres:5432/swordoffice

CMD ["sleep", "infinity"]

# Docker Guide

Docker Compose is the recommended way to run FreeLLMAPI for personal use. The container serves the Express API and the built React dashboard from one process on port 3001, with SQLite persisted in a named volume.

## SwordOffice industry stack (`docker-compose.agent.yml`)

The AI team's infrastructure: a PostgreSQL(+pgvector) database and a private
sandbox machine where team agents work freely.

```bash
docker compose -f docker-compose.agent.yml up -d --build
```

**postgres** (`swordoffice-pg`) — one database `swordoffice` (user `sword`),
schema `office`. Rooms are rows, not databases: 46 personas = 46 rows in
`office.rooms`, all memories in `office.persona_memory`. `services/agent/db.py`
creates the tables on first use; set `SWORDOFFICE_PG` to point at it
(default `postgresql://sword:swordoffice@localhost:5432/swordoffice`).
Data persists in the `pgdata` volume.

**agent-sandbox** (`sword-agent`) — the team's private workstation. Inside it,
agents run as **root with no permission prompts**: node 20, python3, git, and
headless coding CLIs are preinstalled. Isolation comes from the container
boundary — the only host path visible is `./agent-workspace` (mounted at
`/workspace`).

Enable sandbox dispatch for `code_task`:

```bash
AGENT_SANDBOX=docker   # e.g. in .env / config/business/settings env
```

Quick checks:

```bash
docker exec sword-agent node -v                 # toolchain present
echo hi > agent-workspace/hello.txt             # host sees agent's work
docker exec sword-agent psql "$SWORDOFFICE_PG" -c '\dt office.*'
```


## Prerequisites

- Docker
- Docker Compose
- OpenSSL for generating `ENCRYPTION_KEY`

## Quick Start

Create a `.env` file with a 32-byte encryption key:

```bash
ENCRYPTION_KEY="$(openssl rand -hex 32)"
printf "ENCRYPTION_KEY=%s\nPORT=3001\n" "$ENCRYPTION_KEY" > .env
```

Start the app:

```bash
docker compose up -d
```

Open http://localhost:3001, add provider keys on the **Keys** page, then use the generated `freellmapi-...` key with any OpenAI-compatible client.

## Example API Call

```bash
curl http://localhost:3001/v1/chat/completions \
  -H "Authorization: Bearer freellmapi-your-unified-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Say hello from FreeLLMAPI."}]
  }'
```

## Operations

Check status:

```bash
docker compose ps
```

Tail logs:

```bash
docker compose logs -f freellmapi
```

Stop the app:

```bash
docker compose down
```

Update to the latest GHCR image after a release:

```bash
docker compose pull
docker compose up -d
```

Rebuild locally from source:

```bash
docker compose up -d --build
```

## Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `ENCRYPTION_KEY` | Yes | None | 64-character hex key used to encrypt provider API keys at rest. Generate it once and keep it stable. |
| `PORT` | No | `3001` | Host port exposed by Docker Compose. The container listens on port 3001. |

The `freellmapi-data` volume stores SQLite data at `/app/server/data`. Keep the same volume and `ENCRYPTION_KEY` when upgrading, otherwise existing encrypted provider keys cannot be decrypted.

## Published Image

Images are published to GitHub Container Registry:

```bash
docker pull ghcr.io/tashfeenahmed/freellmapi:latest
```

The Docker workflow builds pull requests without pushing. After this repository receives the workflow on `main`, pushes to `main` and version tags publish images to GHCR automatically.

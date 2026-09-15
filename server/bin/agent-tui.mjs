#!/usr/bin/env node
/**
 * FreeLLMAPI agent TUI — an interactive terminal chat against /api/agent.
 *
 * Usage:
 *   agent-tui [--workdir <dir>] [--title <t>] [--model <id|auto>] [--session <id>]
 *
 * Env:
 *   FREELLMAPI_BASE_URL   server base URL (default http://127.0.0.1:3001)
 *   FREELLMAPI_TOKEN      optional Bearer token for the dashboard API
 *
 * Slash commands:
 *   /sessions         list sessions
 *   /new <workdir>    create a fresh session
 *   /model <id|auto>  pin (or unpin) the session model
 *   /tools            show this session's tool catalog
 *   /status           show session settings
 *   /quit             exit
 *
 * Zero external dependencies (Node 18+ fetch/AbortController).
 */
import readline from 'node:readline';
import path from 'node:path';

const BASE = (process.env.FREELLMAPI_BASE_URL ?? 'http://127.0.0.1:3001').replace(/\/$/, '');
const TOKEN = process.env.FREELLMAPI_TOKEN;

const c = {
  dim: (s) => `\x1b[2m${s}\x1b[0m`,
  cyan: (s) => `\x1b[36m${s}\x1b[0m`,
  green: (s) => `\x1b[32m${s}\x1b[0m`,
  red: (s) => `\x1b[31m${s}\x1b[0m`,
  yellow: (s) => `\x1b[33m${s}\x1b[0m`,
  bold: (s) => `\x1b[1m${s}\x1b[0m`,
};

async function api(method, url, body) {
  const res = await fetch(`${BASE}${url}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status} ${url}: ${text.slice(0, 300)}`);
  }
  const ct = res.headers.get('content-type') ?? '';
  return ct.includes('application/json') ? res.json() : res.text();
}

async function listSessions() {
  const { data } = await api('GET', '/api/agent/sessions');
  const rows = data.sessions ?? [];
  if (rows.length === 0) {
    console.log(c.dim('No sessions yet. Use /new <workdir> to create one.'));
    return;
  }
  rows.forEach((s, i) => {
    const model = s.model ? c.cyan(s.model) : c.dim('auto');
    console.log(
      `${c.bold(`[${i}]`)} ${s.id.slice(0, 8)}  ${model.padEnd(18)} ${String(s.messageCount ?? 0).padStart(4)} msgs  ${s.workdir}${s.title ? `  ${c.dim(s.title)}` : ''}`,
    );
  });
}

async function createSession(workdir, title) {
  const { data } = await api('POST', '/api/agent/sessions', {
    workdir: path.resolve(workdir),
    ...(title ? { title } : {}),
  });
  return data;
}

/** Stream a chat message; render tokens live and tool events as compact lines. */
async function chat(session, content, ctrl) {
  const res = await fetch(`${BASE}/api/agent/sessions/${session.id}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
    },
    body: JSON.stringify({ content }),
    signal: ctrl.signal,
  });
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => '');
    console.log(c.red(`Request failed: HTTP ${res.status} ${text.slice(0, 200)}`));
    return;
  }

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  let textOpen = false;
  let currentAnswer = '';
  const toolStartTimes = new Map();

  const flushText = () => {
    if (currentAnswer) process.stdout.write('\n');
    currentAnswer = '';
    textOpen = false;
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const dataLines = frame
        .split('\n')
        .filter((l) => l.startsWith('data: '))
        .map((l) => l.slice(6));
      for (const raw of dataLines) {
        let ev;
        try {
          ev = JSON.parse(raw);
        } catch {
          continue;
        }
        switch (ev.type) {
          case 'start':
            break;
          case 'token':
            if (!textOpen) {
              flushText();
              textOpen = true;
            }
            currentAnswer += ev.delta;
            process.stdout.write(ev.delta);
            break;
          case 'tool_call': {
            flushText();
            toolStartTimes.set(ev.id, Date.now());
            const args = JSON.stringify(ev.arguments);
            const shown = args.length > 120 ? `${args.slice(0, 120)}…` : args;
            process.stdout.write(`\n${c.yellow(`⚙ ${ev.name}`)} ${c.dim(shown)}\n`);
            break;
          }
          case 'tool_result': {
            const t0 = toolStartTimes.get(ev.id);
            const ms = t0 ? `(${(((Date.now() - t0) / 1000).toFixed(1))}s)` : '';
            const badge = ev.ok ? c.green('ok') : c.red('fail');
            const preview = (ev.preview ?? '').split('\n').filter(Boolean).slice(0, 3).join(' | ').slice(0, 200);
            process.stdout.write(`${c.dim('  ↳')} ${badge} ${c.dim(ms)} ${preview ? c.dim(preview) : ''}\n`);
            break;
          }
          case 'done':
            flushText();
            process.stdout.write(c.dim(`\n— done in ${ev.turns} turn(s)\n`));
            break;
          case 'error':
            flushText();
            process.stdout.write(c.red(`error: ${ev.error}${ev.hint ? ` ${c.dim(ev.hint)}` : ''}\n`));
            break;
        }
      }
    }
  }
  flushText();
}

// ---- TUI loop ---------------------------------------------------------------

async function main() {
  const args = process.argv.slice(2);
  const getFlag = (name) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : undefined;
  };

  let session;
  if (getFlag('--session')) {
    session = await api('GET', `/api/agent/sessions/${getFlag('--session')}`).then((r) => r.data);
  } else if (getFlag('--workdir')) {
    session = await createSession(getFlag('--workdir'), getFlag('--title'));
  } else {
    // Show existing sessions, offer to pick or create.
    await listSessions();
    const rl0 = readline.createInterface({ input: process.stdin, output: process.stdout });
    const pick = await new Promise((resolve) =>
      rl0.question(`${c.cyan('Select session # (or "new") to start: ')} `, (a) => resolve(a.trim())),
    );
    rl0.close();
    if (pick === 'new') {
      const wd = await new Promise((resolve) =>
        readline.createInterface({ input: process.stdin, output: process.stdout })
          .question(`${c.cyan('Workdir: ')} `, (a) => resolve(a.trim() || '.')),
      );
      session = await createSession(wd);
    } else if (pick && /^\d+$/.test(pick)) {
      const { data } = await api('GET', '/api/agent/sessions');
      const row = (data.sessions ?? [])[Number(pick)];
      if (!row) {
        console.log(c.red('No such session.'));
        process.exit(1);
      }
      session = row;
    } else {
      console.log(c.red('Pick a session or type "new".'));
      process.exit(1);
    }
  }

  console.log(
    `${c.bold('FreeLLMAPI Agent')}\n` +
      `session ${c.cyan(session.id.slice(0, 8))} · workdir ${session.workdir} · model ${session.model ?? 'auto'} · max ${session.max_turns} turns\n` +
      `${c.dim('Type a task. Slash commands: /sessions /new <dir> /model <id|auto> /tools /status /quit\n')}`,
  );

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const ask = () =>
    new Promise((resolve) =>
      rl.question(c.cyan('you > '), (a) => resolve(a.trim())),
    );

  let current = session;
  while (true) {
    const input = await ask();
    if (!input) continue;

    if (input === '/quit' || input === '/exit') break;
    try {
      if (input === '/sessions') {
        await listSessions();
        continue;
      }
      if (input === '/tools') {
        const { data } = await api('GET', `/api/agent/sessions/${current.id}/tools`);
        for (const t of data.tools ?? []) console.log(`  ${t.name.padEnd(24)} ${c.dim(t.source)}`);
        continue;
      }
      if (input === '/status') {
        const { data } = await api('GET', `/api/agent/sessions/${current.id}`);
        console.log(
          JSON.stringify(
            {
              id: data.id, title: data.title, workdir: data.workdir, model: data.model ?? 'auto',
              max_turns: data.max_turns, tool_deny: data.tool_deny, shell_timeout_ms: data.shell_timeout_ms,
            },
            null, 2,
          ),
        );
        continue;
      }
      if (input.startsWith('/model ')) {
        const m = input.slice(7).trim();
        const model = m === 'auto' ? null : m;
        const { data } = await api('PATCH', `/api/agent/sessions/${current.id}`, { model });
        current = data;
        console.log(c.dim(`model → ${model ?? 'auto'}`));
        continue;
      }
      if (input.startsWith('/new ')) {
        const wd = input.slice(5).trim();
        current = await createSession(wd);
        console.log(c.green(`new session ${current.id.slice(0, 8)} → ${current.workdir}`));
        continue;
      }
      if (input.startsWith('/')) {
        console.log(c.dim('Unknown command. Try /sessions /new /model /tools /status /quit'));
        continue;
      }

      // Regular chat turn.
      const ctrl = new AbortController();
      process.stdout.write(c.dim('\nagent: '));
      await chat(current, input, ctrl);
      process.stdout.write('\n');
    } catch (err) {
      console.log(c.red(`error: ${err.message}`));
      if (/fetch failed|ECONNREFUSED/.test(err.message)) {
        console.log(c.dim(`Is the server running at ${BASE}? (start: npm run dev in server/)`));
      }
    }
  }
  rl.close();
}

main().catch((err) => {
  console.error(c.red(String(err?.message ?? err)));
  process.exit(1);
});

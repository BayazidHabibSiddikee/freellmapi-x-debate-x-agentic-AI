// Business module — an organizational layer on top of the Debate characters.
//
// * Assigns roles (CTO, Project Manager, Engineering Lead, ...) to characters.
// * When a character speaks in a business meeting, their assigned role prompt
//   is APPENDED to their own character prompt (character-driven, role-aware).
// * Business meetings can pull live context from the RAG knowledge library,
//   retrieved with hybrid BM25 + embeddings search.
import { Router, type Request, type Response } from 'express';
import express from 'express';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import {
  indexDocument, listDocuments, deleteDocument, hybridSearch,
  buildRagContext, getDocument, LIBRARY_DIR,
} from '../services/rag.js';
import { sendOk, sendError } from '../lib/envelope.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DATA_DIR = path.resolve(__dirname, '../../../data');
const CHARACTERS_FILE = path.join(DATA_DIR, 'characters.json');
const CONFIG_FILE = path.join(DATA_DIR, 'business_config.json');

// --- role definitions (editable) -------------------------------------------------

interface RoleDef { id: string; title: string; name: string; icon: string; prompt: string; }

const DEFAULT_ROLES: RoleDef[] = [
  {
    id: 'cto', name: 'CTO', title: 'Chief Technology Officer', icon: 'ri-code-box-line',
    prompt: 'You are the Chief Technology Officer. You drive technical strategy, architecture, engineering roadmaps and feasibility. You identify technical risks, push for pragmatic, scalable decisions and speak with senior engineering authority while remaining open to the business goals.',
  },
  {
    id: 'pm', name: 'Project Manager', title: 'Project Manager', icon: 'ri-calendar-check-line',
    prompt: 'You are a Project Manager. You own scope, timeline, milestones, blockers and cross-team coordination. You translate technical and business goals into concrete plans, keep meetings outcome-driven and flag risks early.',
  },
  {
    id: 'eng-lead', name: 'Engineering Lead', title: 'Engineering Lead', icon: 'ri-stack-line',
    prompt: 'You are the Engineering Lead. You own implementation quality, code architecture, testing, and shipping cadence. You are hands-on, pragmatic, and detail-oriented about what can actually be built.',
  },
  {
    id: 'marketing', name: 'CMO', title: 'Chief Marketing Officer', icon: 'ri-megaphone-line',
    prompt: 'You are the Chief Marketing Officer. You own positioning, messaging, go-to-market and growth. You care about audience, differentiation and measurable acquisition channels.',
  },
  {
    id: 'product', name: 'Product Manager', title: 'Product Manager', icon: 'ri-product-hunt-line',
    prompt: 'You are a Product Manager. You represent the customer and the roadmap. You weigh scope, value and effort and push for the smallest thing that delivers real user value.',
  },
  {
    id: 'finance', name: 'CFO', title: 'Chief Financial Officer', icon: 'ri-bank-card-line',
    prompt: 'You are the Chief Financial Officer. You own budget, unit economics, pricing and runway. You challenge ideas that cost too much or have unclear ROI.',
  },
  {
    id: 'ai-ops', name: 'AI Ops', title: 'AI Operations Lead', icon: 'ri-robot-2-line',
    prompt: 'You are the AI Operations Lead. You own model routing, cost per token, reliability and evaluation of AI systems. You are precise about prompt/retrieval quality and observability.',
  },
  {
    id: 'design', name: 'Design Lead', title: 'Design Lead', icon: 'ri-palette-line',
    prompt: 'You are the Design Lead. You own UX/UI quality, visual language and consistency. You advocate for usability, accessibility and delightful details.',
  },
];

interface BusinessConfig {
  roles: RoleDef[];
  assignments: Record<string, string>; // character name -> role id
}

function defaultConfig(): BusinessConfig {
  return { roles: DEFAULT_ROLES, assignments: {} };
}

function loadConfig(): BusinessConfig {
  try {
    if (fs.existsSync(CONFIG_FILE)) {
      const raw = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
      if (!Array.isArray(raw.roles) || raw.roles.length === 0) return defaultConfig();
      return { roles: raw.roles, assignments: raw.assignments || {} };
    }
  } catch { /* fall through */ }
  return defaultConfig();
}

function saveConfig(cfg: BusinessConfig): void {
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(cfg, null, 2));
}

function loadCharacters(): any[] {
  try {
    if (fs.existsSync(CHARACTERS_FILE)) {
      return JSON.parse(fs.readFileSync(CHARACTERS_FILE, 'utf-8'));
    }
  } catch { /* ignore */ }
  return [];
}

export const businessRouter = Router();

// --- config: roles + assignments -----------------------------------------------

// GET /business/api/config
businessRouter.get('/config', (_req: Request, res: Response) => {
  const cfg = loadConfig();
  const chars = loadCharacters().map((c: any) => ({ id: c.id, name: c.name, image: c.image || null }));
  return sendOk(res, { roles: cfg.roles, assignments: cfg.assignments, characters: chars });
});

// PUT /business/api/config
businessRouter.put('/config', (req: Request, res: Response) => {
  const body = req.body as { roles?: RoleDef[]; assignments?: Record<string, string> };
  const cfg = loadConfig();
  if (Array.isArray(body.roles)) cfg.roles = body.roles;
  if (body.assignments && typeof body.assignments === 'object') cfg.assignments = body.assignments;
  saveConfig(cfg);
  return sendOk(res, { roles: cfg.roles, assignments: cfg.assignments });
});

// GET /business/api/roles — the role catalog for assignment dropdowns
businessRouter.get('/roles', (_req: Request, res: Response) => {
  return sendOk(res, { roles: loadConfig().roles });
});
// --- business meeting chat -----------------------------------------------------

// pick the next speaker deterministically, mirroring the debate round logic
function nextSpeaker(
  participants: string[],
  history: Array<{ speaker: string; text: string }>,
  mode: string,
  forced?: string,
): string {
  if (forced) return forced;
  if (!participants.length) return 'User';
  if (mode === 'round_robin' && history.length) {
    const idx = participants.indexOf(history[history.length - 1].speaker);
    if (idx !== -1) return participants[(idx + 1) % participants.length];
  } else if (mode === 'random') {
    return participants[Math.floor(Math.random() * participants.length)];
  }
  return participants[0];
}

// POST /business/api/chat
businessRouter.post('/chat', async (req: Request, res: Response) => {
  const body = req.body as {
    topic: string;
    participants: string[];
    history: Array<{ speaker: string; text: string }>;
    user_name?: string;
    mode?: string;
    forced_speaker?: string;
    use_rag?: boolean;
  };
  const { topic, participants, history, user_name, mode, forced_speaker, use_rag } = body;
  if (!participants || participants.length === 0) {
    return sendError(res, 400, 'No participants selected', {
      hint: 'POST /business/api/chat { topic: string, participants: string[] (min 1), history?: [{speaker,text}] }',
      retryable: true,
    });
  }
  const cfg = loadConfig();
  const speaker = nextSpeaker(participants, history || [], mode || 'round_robin', forced_speaker);
  const chars = loadCharacters();
  const charObj = chars.find((c: any) => c.name === speaker);
  const charPrompt = charObj?.system_prompt || `You are ${speaker}.`;

  // Role prompt appended to the character prompt when one is assigned.
  const roleId = cfg.assignments[speaker];
  const role = cfg.roles.find((r) => r.id === roleId);
  const roleBlock = role
    ? `\n\n[Business Role: ${role.name} — ${role.title}]\n${role.prompt}`
    : '\n\n[Business Role: Unassigned — speak from your character perspective as a team member.]';

  // RAG context from the hybrid knowledge library (retrieved for this topic).
  const ragContext = use_rag ? buildRagContext(`${topic} ${history?.slice(-3).map(h => h.text).join(' ')}`, 4) : '';

  const base = `You are in a business strategy meeting about "${topic}". Participants: ${participants.join(', ')} and ${user_name || 'User'}. You are speaking as ${speaker}.\n\nCharacter identity: ${charPrompt}${roleBlock}\n\n` +
    `Meeting rules: 1) Stay in character ALWAYS — keep your personality, tone and quirks. 2) Operate from within your assigned business role (if any). 3) Do NOT prefix with your name. 4) Respond conversationally (1-4 sentences). 5) Be decisive, give your point of view, and address others by name when relevant.${ragContext}`;

  const messages: Array<{ role: string; content: string }> = [{ role: 'system', content: base }];
  for (const msg of (history || []).slice(-8)) {
    if (msg.speaker === speaker) messages.push({ role: 'assistant', content: msg.text });
    else messages.push({ role: 'user', content: `[${msg.speaker}]: ${msg.text}` });
  }

  const apiKey = process.env.FREELLMAPI_KEY || '';
  try {
    const proxyRes = await fetch('http://localhost:3001/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}) },
      body: JSON.stringify({ model: 'auto', messages, max_tokens: 300 }),
    });
    if (!proxyRes.ok) {
      const errText = await proxyRes.text();
      return sendError(res, proxyRes.status, `LLM error: ${errText.slice(0, 200)}`, {
        hint: 'The upstream LLM proxy rejected the completion — verify the model catalog and API key, then retry.',
        retryable: true,
      });
    }
    const data: any = await proxyRes.json();
    const msg = data.choices?.[0]?.message || {};
    let reply: string = msg.content || '[Error: empty response]';

    // Strip leaked reasoning from content (same strategy as the debate route).
    const reasoningPrefixes = [
      /(?:^|\n)\s*(?:We need to|The user|I need to|Let me|Thinking|As .*|Should we|First,)\s.*?(?=\n\s*[A-Z])/,
      /(?:^|\n)\s*.*(?:roleplay|must respond|core traits|system instructions).*?(?=\n\s*[A-Z])/i,
    ];
    for (const pattern of reasoningPrefixes) {
      const match = reply.match(pattern);
      if (match) { reply = reply.substring((match.index ?? 0) + match[0].length).trim(); break; }
    }
    if (/^(We need|The user|I need to|Let me|Thinking)/i.test(reply)) {
      const sentences = reply.split(/(?<=[.!?])\s+/);
      for (let i = 0; i < sentences.length; i++) {
        if (!/^(We need|The user|I need|Let me|Thinking|As .*|.*roleplay)/i.test(sentences[i])) {
          reply = sentences.slice(i).join(' '); break;
        }
      }
    }

    // GPT-OSS and some reasoning models leak their full chain-of-thought INTO the
    // content field. Detect the tell-tale self-referential meta-reasoning and
    // pull out the actual spoken answer instead.
    if (/we only have system|user content is not provided|the assistant must|must (abide|obey|follow).*polic|disallowed content|we must not|we have to obey/i.test(reply)) {
      const quoted = reply.match(/["“]([^"”]{15,}?)["”]/g) || [];
      const splitOnInstructions = reply.split(/\b(?:Thus|Therefore|Respond|Response|So),?:/).map((s: string) => s.trim()).filter(s => s);
      const sayers = [...quoted, ...reply.split(/(?<=[.!?])\s+/), ...splitOnInstructions]
        .filter(s => s && !/we only have system|user content is not provided|must (abide|obey|follow)|disallowed content|we must not|we have to obey|essay|analysis/i.test(s) && s.length > 15);
      if (sayers.length) {
        const quotedAnswer = quoted.find(s => !/polic|disallowed|must not/i.test(s) && s.length > 15);
        const cleanest = sayers.reduce((a, b) => (b.length > a.length ? b : a));
        const chosen = quotedAnswer || cleanest;
        const cleaned = String(chosen).replace(/^["“]|["”]$/g, '').trim();
        if (cleaned) reply = cleaned;
      }
    }

    return sendOk(res, { speaker, role: role ? role.name : null, text: reply, rag: { applied: ragContext.length > 0 } });
  } catch (e: any) {
    return sendError(res, 502, `Connection failed: ${e.message}`, {
      hint: 'The LLM proxy at localhost:3001 is unreachable — start the server (npm run dev) and retry.',
      retryable: true,
    });
  }
});
// --- knowledge library (RAG upload + hybrid search) -----------------------------

// GET /business/api/rag_report — indexed library summary (reused by Knowledge page)
businessRouter.get('/rag_report', (_req: Request, res: Response) => {
  const docs = listDocuments();
  return sendOk(res, {
    total: docs.length,
    indexed: docs.map((d) => d.name),
    documents: docs,
  });
});

// GET /business/api/library
businessRouter.get('/library', (_req: Request, res: Response) => {
  return sendOk(res, { documents: listDocuments() });
});

businessRouter.post('/upload', express.raw({ type: ['multipart/form-data'], limit: '30mb' }), (req: Request, res: Response) => {
  const contentType = req.headers['content-type'] || '';
  const boundaryMatch = contentType.match(/boundary=(?:"([^"]+)"|([^;\s]+))/);
  if (!boundaryMatch) return sendError(res, 400, 'Invalid content type', { hint: 'Send multipart/form-data with a boundary and a "file" part.', retryable: true });
  const boundary = boundaryMatch[1] || boundaryMatch[2];
  const rawBody = req.body as Buffer;

  let filename = '';
  let fileData: Buffer | null = null;
  const parts = rawBody.toString('binary').split(`--${boundary}`).map(p => Buffer.from(p, 'binary'));
  for (const part of parts) {
    const headerEndIdx = part.indexOf('\r\n\r\n');
    if (headerEndIdx === -1) continue;
    const headers = part.subarray(0, headerEndIdx).toString('latin1');
    const fnameMatch = headers.match(/filename="([^"]+)"/);
    if (!fnameMatch) continue;
    if (!headers.includes('name="file"')) continue;
    filename = fnameMatch[1];
    // Trim trailing CRLF that belongs to the multipart framing.
    let body = part.subarray(headerEndIdx + 4);
    while (body.length && (body[body.length - 1] === 13 || body[body.length - 1] === 10)) body = body.subarray(0, body.length - 1);
    fileData = body.length ? body : null;
    break;
  }
  if (!fileData || !filename) return sendError(res, 400, 'No file provided', { hint: 'Include a multipart part named "file".', retryable: true });
  const allowed = /\.(md|txt|docx|pdf|html|json|markdown|csv)$/i;
  if (!allowed.test(filename)) return sendError(res, 400, 'Unsupported file type (use .md, .txt, .docx, .pdf, .html, .json, .csv)', { hint: 'Convert the document to one of the supported extensions and retry.', retryable: true });
  if (fileData.length > 25 * 1024 * 1024) return sendError(res, 413, 'File too large (max 25MB)', { hint: 'Split the document into smaller parts and upload each separately.', retryable: false });

  const doc = indexDocument(filename, fileData);
  return sendOk(res, { status: 'success', message: `Indexed "${doc.name}" (${doc.chunks.length} chunks)`, id: doc.id, ...(doc.note ? { note: doc.note } : {}) });
});

// GET /business/api/library/:id — doc metadata + full text
businessRouter.get('/library/:id', (req: Request, res: Response) => {
  const doc = getDocument(String(req.params.id));
  if (!doc) return sendError(res, 404, 'Document not found', { hint: 'GET /business/api/library lists valid ids.', retryable: false });
  return sendOk(res, { id: doc.id, name: doc.name, ext: doc.ext, size: doc.size, uploadedAt: doc.uploadedAt, note: doc.note, text: doc.text });
});

// GET /business/api/library/:id/file — serve the original uploaded bytes
businessRouter.get('/library/:id/file', (req: Request, res: Response) => {
  const doc = getDocument(String(req.params.id));
  if (!doc) return sendError(res, 404, 'Document not found', { hint: 'GET /business/api/library lists valid ids.', retryable: false });
  const p = path.join(LIBRARY_DIR, 'files', `${doc.id}${doc.ext}`);
  if (!fs.existsSync(p)) return sendError(res, 404, 'File missing', { hint: 'Metadata exists but the original bytes were removed — re-upload the document.', retryable: true });
  res.sendFile(p);
});

// DELETE /business/api/library/:id
businessRouter.delete('/library/:id', (req: Request, res: Response) => {
  const ok = deleteDocument(String(req.params.id));
  if (!ok) return sendError(res, 404, 'Document not found', { hint: 'GET /business/api/library lists valid ids.', retryable: false });
  return sendOk(res, { deleted: true });
});

// POST /business/api/search — hybrid BM25 + embeddings retrieval
businessRouter.post('/search', (req: Request, res: Response) => {
  const body = req.body as { query?: string; top_k?: number };
  const query = (body.query || '').trim();
  if (!query) return sendError(res, 400, 'Missing query', { hint: 'POST /business/api/search { query: string, top_k?: number }', retryable: true });
  const topK = Math.min(20, Math.max(1, body.top_k || 6));
  const results = hybridSearch(query, topK);
  return sendOk(res, { count: results.length, results, pagination: { total: results.length, limit: topK } });
});

// GET /business/api/health
businessRouter.get('/health', (_req: Request, res: Response) => {
  return sendOk(res, {
    status: 'operational',
    roles: loadConfig().roles.length,
    characters: loadCharacters().length,
    indexed_documents: listDocuments().length,
  });
});
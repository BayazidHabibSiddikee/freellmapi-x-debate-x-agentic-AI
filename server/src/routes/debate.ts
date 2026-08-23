import { Router, type Request, type Response } from 'express';
import express from 'express';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import {
  indexDocument, listDocuments, deleteDocument, hybridSearch, buildRagContext,
} from '../services/rag.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DATA_DIR = path.resolve(__dirname, '../../../data');
const CHARACTERS_FILE = path.join(DATA_DIR, 'characters.json');
const SESSIONS_DIR = path.join(DATA_DIR, 'debate_sessions');
const IMAGES_DIR = path.join(DATA_DIR, 'images');
const EXPORTS_DIR = path.join(DATA_DIR, 'exports');

for (const d of [SESSIONS_DIR, IMAGES_DIR, EXPORTS_DIR]) {
  fs.mkdirSync(d, { recursive: true });
}

let CHARACTERS: any[] = [];
function loadCharacters(): any[] {
  try {
    if (fs.existsSync(CHARACTERS_FILE)) {
      CHARACTERS = JSON.parse(fs.readFileSync(CHARACTERS_FILE, 'utf-8'));
    }
  } catch { /* use defaults */ }
  return CHARACTERS;
}
loadCharacters();

export const debateRouter = Router();

// GET /debate/api/characters
debateRouter.get('/characters', (_req: Request, res: Response) => {
  const chars = loadCharacters();
  const safe = chars.map((c: any) => ({ id: c.id, name: c.name, image: c.image || null }));
  res.json(safe);
});

// POST /debate/api/chat
debateRouter.post('/chat', async (req: Request, res: Response) => {
  const body = req.body as {
    topic: string; characters: string[]; history: Array<{speaker: string; text: string}>;
    user_name: string; mode: string; forced_speaker: string; scene?: string;
  };
  const { topic, characters, history, user_name, mode, forced_speaker, scene } = body;
  if (!characters || characters.length === 0) {
    return res.status(400).json({ error: 'No characters selected' });
  }
  let nextCharName = forced_speaker || characters[0];
  if (mode === 'round_robin' && history.length > 0) {
    const lastSpeaker = history[history.length - 1].speaker;
    const idx = characters.indexOf(lastSpeaker);
    if (idx !== -1) nextCharName = characters[(idx + 1) % characters.length];
  } else if (mode === 'random') {
    nextCharName = characters[Math.floor(Math.random() * characters.length)];
  }
  const chars = loadCharacters();
  const charObj = chars.find((c: any) => c.name === nextCharName);
  const systemPrompt = charObj?.system_prompt || `You are ${nextCharName}.`;
  const userName = user_name || 'User';
  const messages: Array<{role: string; content: string}> = [
    { role: 'system', content: `You are in a group chat debate about "${topic}". Participants: ${characters.join(', ')} and ${userName}. You are roleplaying as ${nextCharName}. Personality: ${systemPrompt}. Rules: 1) Stay in character ALWAYS. 2) Do NOT prefix with your name. 3) Respond conversationally (1-4 sentences). 4) Address others by name when relevant. 5) Be passionate, disagree when your character would disagree.` },
  ];
  for (const msg of history.slice(-8)) {
    if (msg.speaker === nextCharName) {
      messages.push({ role: 'assistant', content: msg.text });
    } else {
      messages.push({ role: 'user', content: `[${msg.speaker}]: ${msg.text}` });
    }
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
      return res.status(proxyRes.status).json({ error: `LLM error: ${errText.slice(0, 200)}` });
    }
    const data: any = await proxyRes.json();
    const msg = data.choices?.[0]?.message || {};
    let reply = msg.content || '[Error: empty response]';
    
    // AGGRESSIVE cleanup: strip reasoning that leaks into content field
    // Models like GPT-OSS include reasoning in content, not just in 'reasoning' field
    const reasoningPrefixes = [
      /(?:^|\n)\s*(?:We need to|The user|I need to|Let me|Thinking|As .*|Should we|First,)\s.*?(?=\n\s*[A-Z])/,
      /(?:^|\n)\s*.*(?:roleplay|must respond|core traits|system instructions).*?(?=\n\s*[A-Z])/i,
    ];
    
    for (const pattern of reasoningPrefixes) {
      const match = reply.match(pattern);
      if (match) {
        reply = reply.substring(match.index + match[0].length).trim();
        break;
      }
    }
    
    // If still has reasoning at start, try to extract first substantive sentence
    if (/^(We need|The user|I need|Let me|Thinking)/i.test(reply)) {
      const sentences = reply.split(/(?<=[.!?])\s+/);
      for (let i = 0; i < sentences.length; i++) {
        if (!/^(We need|The user|I need|Let me|Thinking|As .*|.*roleplay)/i.test(sentences[i])) {
          reply = sentences.slice(i).join(' ');
          break;
        }
      }
    }
    
    // GPT-OSS / reasoning models leak chain-of-thought into content. Detect the
    // tell-tale meta-reasoning and pull out the actual spoken answer.
    if (/we only have system|user content is not provided|the assistant must|must (abide|obey|follow).*polic|disallowed content|we must not|we have to obey/i.test(reply)) {
      const quoted: string[] = reply.match(/["“]([^"”]{15,}?)["”]/g) || [];
      const splitOnInstructions = reply.split(/\b(?:Thus|Therefore|Respond|Response|So),?:/).map((s: string) => s.trim()).filter((s: string) => s);
      const sayers = [...quoted, ...reply.split(/(?<=[.!?])\s+/), ...splitOnInstructions]
        .filter((s: string) => s && !/we only have system|user content is not provided|must (abide|obey|follow)|disallowed content|we must not|we have to obey|essay|analysis/i.test(s) && s.length > 15);
      if (sayers.length) {
        const quotedAnswer = quoted.find(s => !/polic|disallowed|must not/i.test(s) && s.length > 15);
        const cleanest = sayers.reduce((a, b) => (b.length > a.length ? b : a));
        const cleaned = String(quotedAnswer || cleanest).replace(/^["“]|["”]$/g, '').trim();
        if (cleaned) reply = cleaned;
      }
    }

    res.json({ speaker: nextCharName, text: reply });
  } catch (e: any) {
    res.status(502).json({ error: `Connection failed: ${e.message}` });
  }
});

// POST /debate/api/sync_session
debateRouter.post('/sync_session', (req: Request, res: Response) => {
  const body = req.body as { session_id: string; topic: string; characters: string[]; history: any[] };
  const { session_id, topic, characters, history } = body;
  if (!session_id) return res.json({ status: 'ignored' });
  const filePath = path.join(SESSIONS_DIR, `${session_id}.json`);
  fs.writeFileSync(filePath, JSON.stringify({ session_id, topic, participants: characters, updated_at: new Date().toISOString(), history }, null, 2));
  res.json({ status: 'success' });
});

// GET /debate/api/sessions
debateRouter.get('/sessions', (_req: Request, res: Response) => {
  const files = fs.readdirSync(SESSIONS_DIR).filter((f: string) => f.endsWith('.json'));
  const sessions = files.map((f: string) => {
    try {
      const data = JSON.parse(fs.readFileSync(path.join(SESSIONS_DIR, f), 'utf-8'));
      return { id: data.session_id, topic: data.topic, updated_at: data.updated_at, turns: data.history?.length ?? 0 };
    } catch { return null; }
  }).filter(Boolean);
  const sorted = [...sessions].sort((a: any, b: any) => (b.updated_at < a.updated_at ? 1 : -1));
  res.json(sorted);
});

// POST /debate/api/export
debateRouter.post('/export', (req: Request, res: Response) => {
  const body = req.body as { topic: string; characters: string[]; history: any[] };
  const { topic, characters, history } = body;
  const ts = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `debate_${ts}.md`;
  let md = `# Debate Transcript\n\n**Topic:** ${topic}\n**Participants:** ${characters.join(', ')}\n**Date:** ${new Date().toLocaleString()}\n\n---\n\n`;
  for (const msg of history) { md += `**[${msg.speaker}]**: ${msg.text}\n\n`; }
  const filePath = path.join(EXPORTS_DIR, filename);
  fs.writeFileSync(filePath, md, 'utf-8');
  res.json({ status: 'success', file: `/debate/exports/${filename}` });
});

// GET /debate/api/exports/:filename
debateRouter.get('/exports/:filename', (req: Request, res: Response) => {
  const filename = req.params.filename as string;
  if (filename.includes('..') || filename.includes('/') || filename.includes('\\')) {
    return res.status(400).json({ error: 'Invalid filename' });
  }
  const filePath = path.join(EXPORTS_DIR, filename);
  if (fs.existsSync(filePath)) { res.sendFile(filePath); }
  else { res.status(404).json({ error: 'File not found' }); }
});

// POST /debate/api/upload_character
debateRouter.post('/upload_character', async (req: Request, res: Response) => {
  const contentType = req.headers['content-type'] || '';
  const boundaryMatch = contentType.match(/boundary=(?:"([^"]+)"|([^;\s]+))/);
  if (!boundaryMatch) return res.status(400).json({ error: 'Invalid content type' });
  const boundary = boundaryMatch[1] || boundaryMatch[2];
  const rawBody = req.body as Buffer;
  const parts = rawBody.toString('binary').split(`--${boundary}`);
  let filename = 'character.png';
  let imageData = Buffer.alloc(0);
  for (const part of parts) {
    if (part.includes('filename=')) {
      const fnameMatch = part.match(/filename="([^"]+)"/);
      if (fnameMatch) filename = fnameMatch[1];
    }
    if (part.trim() && !part.includes('filename=') && !part.includes('--')) {
      const lines = part.split('\r\n');
      let contentStart = 0;
      for (let i = 0; i < lines.length; i++) { if (lines[i].trim() === '') { contentStart = i + 1; break; } }
      imageData = Buffer.from(lines.slice(contentStart).join('\r\n'), 'binary');
    }
  }
  if (imageData.length === 0) return res.status(400).json({ error: 'No image data' });
  const safeName = filename.replace(/[^a-zA-Z0-9._-]/g, '_');
  const destPath = path.join(IMAGES_DIR, safeName);
  fs.writeFileSync(destPath, imageData);
  const chars = loadCharacters();
  const baseName = safeName.replace('.png', '');
  chars.push({ id: String(chars.length + 1), name: baseName, image: `/images/${safeName}`, system_prompt: `You are ${baseName}. Respond in character.` });
  fs.writeFileSync(CHARACTERS_FILE, JSON.stringify(chars, null, 2));
  res.json({ status: 'success', message: `Character "${baseName}" added.` });
});

// GET /debate/api/health
debateRouter.get('/health', (_req: Request, res: Response) => {
  res.json({ status: 'operational', characters_loaded: loadCharacters().length, sessions_count: fs.readdirSync(SESSIONS_DIR).filter((f: string) => f.endsWith('.json')).length });
});

// -------------------------------------------------------------------------
// Knowledge hub — RAG library (hybrid BM25 + embeddings). These power the
// /knowledge page and are shared with the Business module.
// -------------------------------------------------------------------------

// POST /debate/api/upload_knowledge — multipart file upload (md/txt/docx/pdf)
debateRouter.post('/upload_knowledge', express.raw({ type: ['multipart/form-data'], limit: '30mb' }), (req: Request, res: Response) => {
  const contentType = req.headers['content-type'] || '';
  const boundaryMatch = contentType.match(/boundary=(?:"([^"]+)"|([^;\s]+))/);
  if (!boundaryMatch) return res.status(400).json({ error: { message: 'Invalid content type' } });
  const boundary = boundaryMatch[1] || boundaryMatch[2];
  const rawBody = req.body as Buffer;

  let filename = '';
  let fileData: Buffer | null = null;
  const parts = rawBody.toString('binary').split(`--${boundary}`).map(p => Buffer.from(p, 'binary'));
  for (const part of parts) {
    const headerEndIdx = part.indexOf('\r\n\r\n');
    if (headerEndIdx === -1) continue;
    const headers = part.subarray(0, headerEndIdx).toString('latin1');
    if (!headers.includes('name="file"')) continue;
    const fnameMatch = headers.match(/filename="([^"]+)"/);
    if (!fnameMatch) continue;
    filename = fnameMatch[1];
    let body = part.subarray(headerEndIdx + 4);
    while (body.length && (body[body.length - 1] === 13 || body[body.length - 1] === 10)) body = body.subarray(0, body.length - 1);
    fileData = body.length ? body : null;
    break;
  }
  if (!fileData || !filename) return res.status(400).json({ error: { message: 'No file provided' } });
  const allowed = /\.(md|txt|docx|pdf|html|json|markdown|csv)$/i;
  if (!allowed.test(filename)) return res.status(400).json({ error: { message: 'Unsupported file type' } });

  const doc = indexDocument(filename, fileData);
  res.json({ status: 'success', message: `Indexed "${doc.name}"`, id: doc.id, ...(doc.note ? { note: doc.note } : {}) });
});

// GET /debate/api/rag_report — indexed library listing
debateRouter.get('/rag_report', (_req: Request, res: Response) => {
  const docs = listDocuments();
  res.json({ indexed: docs.map((d) => d.name), documents: docs, total: docs.length });
});

// POST /debate/api/knowledge_search — hybrid BM25 + embeddings retrieval
debateRouter.post('/knowledge_search', (req: Request, res: Response) => {
  const query = (req.body?.query || '').trim();
  if (!query) return res.status(400).json({ error: { message: 'Missing query' } });
  const results = hybridSearch(query, 8);
  res.json({ count: results.length, results });
});

// DELETE /debate/api/rag/:id — remove an indexed document
debateRouter.delete('/rag/:id', (req: Request, res: Response) => {
  const ok = deleteDocument(String(req.params.id));
  if (!ok) return res.status(404).json({ error: { message: 'Document not found' } });
  res.json({ success: true });
});

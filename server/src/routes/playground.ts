import { Router, type Request, type Response } from 'express';
import fs from 'fs';
import path from 'path';

const HISTORY_PATH = path.resolve(import.meta.dirname, '../../data/playground_history.json');

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  meta?: { platform?: string; model?: string; latency?: number; fallbackAttempts?: number };
}

interface HistoryEntry {
  id: string;
  createdAt: number;
  model: string;
  messages: ChatMessage[];
  firstUserMessage: string;
}

function readHistory(): HistoryEntry[] {
  try {
    const raw = fs.readFileSync(HISTORY_PATH, 'utf-8');
    return JSON.parse(raw) as HistoryEntry[];
  } catch { return []; }
}

function writeHistory(entries: HistoryEntry[]) {
  // Keep max 50 entries to avoid bloating the file
  const trimmed = entries.slice(0, 50);
  fs.writeFileSync(HISTORY_PATH, JSON.stringify(trimmed, null, 2), 'utf-8');
}

export const playgroundRouter = Router();

// GET /api/playground/history — list all conversation histories
playgroundRouter.get('/history', (_req: Request, res: Response) => {
  res.json(readHistory());
});

// POST /api/playground/history — save or update a conversation
playgroundRouter.post('/history', (req: Request, res: Response) => {
  const { id, createdAt, model, messages, firstUserMessage } = req.body as HistoryEntry & { firstUserMessage: string };
  if (!id || !messages?.length) {
    res.status(400).json({ error: { message: 'id and messages are required', type: 'invalid_request_error' } });
    return;
  }
  const existing = readHistory().filter(h => h.id !== id);
  const entry: HistoryEntry = {
    id,
    createdAt: createdAt ?? Date.now(),
    model: model ?? 'auto',
    messages,
    firstUserMessage,
  };
  writeHistory([entry, ...existing]);
  res.json(entry);
});

// DELETE /api/playground/history/:id — delete a single entry
playgroundRouter.delete('/history/:id', (req: Request, res: Response) => {
  const { id } = req.params;
  const updated = readHistory().filter(h => h.id !== id);
  writeHistory(updated);
  res.json({ deleted: id, remaining: updated.length });
});

// DELETE /api/playground/history — clear all history
playgroundRouter.delete('/history', (_req: Request, res: Response) => {
  writeHistory([]);
  res.json({ cleared: true });
});

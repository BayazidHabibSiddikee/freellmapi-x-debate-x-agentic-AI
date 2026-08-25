import express from 'express';
import fs from 'fs';
import cors from 'cors';
import helmet from 'helmet';
import path from 'path';
import { fileURLToPath } from 'url';
import { keysRouter } from './routes/keys.js';
import { modelsRouter } from './routes/models.js';
import { proxyRouter } from './routes/proxy.js';
import { responsesRouter } from './routes/responses.js';
import { fallbackRouter } from './routes/fallback.js';
import { embeddingsRouter } from './routes/embeddings.js';
import { analyticsRouter } from './routes/analytics.js';
import { healthRouter } from './routes/health.js';
import { settingsRouter } from './routes/settings.js';
import { premiumRouter } from './routes/premium.js';
import { playgroundRouter } from './routes/playground.js';
import { rateLimitRouter } from './routes/rateLimits.js';
import { debateRouter } from './routes/debate.js';
import { businessRouter } from './routes/business.js';
import { createProxyRateLimiter } from './middleware/rateLimit.js';
import { errorHandler } from './middleware/errorHandler.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const DEFAULT_DASHBOARD_ORIGINS = [
  'http://localhost:5173',
  'http://127.0.0.1:5173',
  'http://[::1]:5173',
];

function getAllowedCorsOrigins() {
  const configuredOrigins = (process.env.DASHBOARD_ORIGINS ?? '')
    .split(',')
    .map(origin => origin.trim())
    .filter(Boolean);

  return new Set([...DEFAULT_DASHBOARD_ORIGINS, ...configuredOrigins]);
}

export function createApp() {
  const app = express();
  const allowedCorsOrigins = getAllowedCorsOrigins();

  // CSP intentionally disabled — the SPA bundles inline styles and the OG
  // image is loaded from the same origin; enabling helmet's default CSP
  // breaks the React build's hashed-asset loader. HSTS off because this is
  // a single-user local proxy, served over HTTP on localhost. Both should
  // stay disabled unless someone serves the proxy over HTTPS publicly
  // (which is also not a supported deployment — see README).
  app.use(helmet({ contentSecurityPolicy: false, hsts: false }));
  app.use(cors({
    origin(origin: string | undefined, callback: (err: Error | null, allow?: boolean) => void) {
      callback(null, !origin || allowedCorsOrigins.has(origin));
    },
  }));
  // 10mb: code agents (OpenCode, AionUI, Qwen Code) ship very large system
  // prompts + tool schemas + repo context; 1mb cut their sessions off
  // mid-conversation with an opaque 413. (#200)
  app.use(express.json({ limit: '10mb' }));

  // Dashboard auth removed — running locally behind localhost-only binding.
  // The /v1 proxy keeps its own unified-API-key auth for app clients.
  // All /api/* admin routes are now open (localhost-bound server = no external access).

  // Playground history — persisted as JSON on disk
  app.use('/api/playground', playgroundRouter);

  // Rate limit tracking — real-time per-model usage vs limits
  app.use('/api/rate-limits', rateLimitRouter);

  // API routes — open, no login required.
  app.use('/api/keys', keysRouter);
  app.use('/api/models', modelsRouter);
  app.use('/api/fallback', fallbackRouter);
  app.use('/api/embeddings', embeddingsRouter);
  app.use('/api/analytics', analyticsRouter);
  app.use('/api/health', healthRouter);
  app.use('/api/settings', settingsRouter);
  app.use('/api/premium', premiumRouter);


  // OpenAI-compatible proxy. Per-IP rate limiting (#35 item #6) runs first so
  // it throttles unauthenticated brute-force / flood attempts before any
  // routing work. Tune via PROXY_RATE_LIMIT_RPM; 0 disables it.
  app.use('/v1', createProxyRateLimiter());
  app.use('/v1', proxyRouter);
  // OpenAI Responses API shim (Codex CLI requires wire_api="responses"; see #96)
  app.use('/v1', responsesRouter);

  // Health check
  app.get('/api/ping', (_req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
  });

  // Error handler (for API routes)
  app.use(errorHandler);

  // Debate Simulator (merged from AI_Debate)
  app.use('/debate/api', debateRouter);
  app.use('/debate/images', express.static(path.resolve(__dirname, '../../data/images')));
  app.use('/debate/exports', express.static(path.resolve(__dirname, '../../data/exports')));

  // Shared design-language stylesheet for all template surfaces
  app.get('/theme.css', (_req, res) => {
    res.type('text/css').sendFile(path.resolve(__dirname, '../../docs/theme.css'));
  });
  // Serve character images at both /debate/images/ and /images/ for template compatibility
  app.use('/images', express.static(path.resolve(__dirname, '../../data/images')));
  
  // API route aliases for backward compatibility
  app.use('/api', debateRouter);

  // Business module — role assignments + hybrid RAG meeting chat
  app.use('/business/api', businessRouter);
  app.use('/api/business', businessRouter);
  app.use('/business/library-files', express.static(path.resolve(__dirname, '../../data/library/files')));
  
  app.get('/knowledge', (_req, res) => {
    const templatePath = path.resolve(__dirname, '../../docs/knowledge.html');
    if (fs.existsSync(templatePath)) res.sendFile(templatePath);
    else res.status(404).send('Knowledge page not found');
  });
  
  app.get('/personal', (_req, res) => {
    const templatePath = path.resolve(__dirname, '../../docs/personal.html');
    if (fs.existsSync(templatePath)) {
      res.sendFile(templatePath);
    } else {
      res.status(404).send('Personal chat not found');
    }
  });
  
  app.get('/debate', (_req, res) => {
    const templatePath = path.resolve(__dirname, '../../docs/debate.html');
    if (fs.existsSync(templatePath)) {
      res.sendFile(templatePath);
    } else {
      res.status(404).send('Debate module not found');
    }
  });

  app.get('/business', (_req, res) => {
    const templatePath = path.resolve(__dirname, '../../docs/business.html');
    if (fs.existsSync(templatePath)) {
      res.sendFile(templatePath);
    } else {
      res.status(404).send('Business module not found');
    }
  });

    // Serve client static files (after API error handler). CLIENT_DIST lets
  // embedders relocate the built dashboard (e.g. the desktop app ships it in
  // extraResources, where the __dirname-relative path can't reach).
  const clientDist = process.env.CLIENT_DIST
    ? path.resolve(process.env.CLIENT_DIST)
    : path.resolve(__dirname, '../../client/dist');
  app.use(express.static(clientDist));
  // SPA fallback — serve index.html for non-API routes
  app.use((req, res, next) => {
    if (req.path.startsWith('/api/') || req.path.startsWith('/v1/')) {
      next();
      return;
    }
    res.sendFile(path.join(clientDist, 'index.html'));
  });

  return app;
}

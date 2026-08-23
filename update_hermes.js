const fs = require('fs');
const path = require('path');
const Database = require('better-sqlite3');
const crypto = require('crypto');

// 1. Decrypt keys from freellmapi
const envKey = 'c5e11218c48156f2e3d507528bfaf0ed4dd1072704554e7e5211831ffa5e333c';
const key = Buffer.from(envKey, 'hex');

const db = new Database(path.join(__dirname, 'server/data/freeapi.db'));
const rows = db.prepare('SELECT platform, encrypted_key, iv, auth_tag FROM api_keys').all();

const decryptedKeys = [];

for (const row of rows) {
    try {
        const decipher = crypto.createDecipheriv('aes-256-gcm', key, Buffer.from(row.iv, 'hex'));
        decipher.setAuthTag(Buffer.from(row.auth_tag, 'hex'));
        let decrypted = decipher.update(row.encrypted_key, 'hex', 'utf8');
        decrypted += decipher.final('utf8');
        decryptedKeys.push({ platform: row.platform, key: decrypted });
    } catch (e) {
        console.error(`Failed to decrypt for ${row.platform}:`, e.message);
    }
}

// 2. Map platforms to Hermes providers and base URLs
const mapping = {
  'openrouter': { id: 'openrouter', base: 'https://openrouter.ai/api/v1' },
  'ollama': { id: 'ollama-cloud', base: 'https://api.ollama.com/v1' },
  'opencode': { id: 'opencode-zen', base: 'https://api.opencode.com/v1' },
  'huggingface': { id: 'huggingface', base: 'https://router.huggingface.co/v1' },
  'zhipu': { id: 'zai', base: 'https://open.bigmodel.cn/api/paas/v4' },
  'google': { id: 'gemini', base: 'https://generativelanguage.googleapis.com/v1beta' },
  'groq': { id: 'custom:groq', base: 'https://api.groq.com/openai/v1' },
  'cerebras': { id: 'custom:cerebras', base: 'https://api.cerebras.ai/v1' },
  'mistral': { id: 'custom:mistral', base: 'https://api.mistral.ai/v1' },
  'ovh': { id: 'custom:ovh', base: 'https://endpoints.ai.cloud.ovh.net/v1' }
};

// 3. Read auth.json
const authJsonPath = path.join(process.env.HOME, '.hermes', 'auth.json');
let authJson = { version: 1, providers: {}, credential_pool: {} };
if (fs.existsSync(authJsonPath)) {
  authJson = JSON.parse(fs.readFileSync(authJsonPath, 'utf8'));
}
if (!authJson.credential_pool) authJson.credential_pool = {};

// Clean up any bad entries from previous run
for (const [poolId, credentials] of Object.entries(authJson.credential_pool)) {
  authJson.credential_pool[poolId] = credentials.filter(c => c.access_token && !c.access_token.includes('Error decrypting'));
}

const generateUUID = () => crypto.randomBytes(3).toString('hex'); // 6 chars hex for ID

for (const dk of decryptedKeys) {
  let providerId, baseUrl, actualKey;
  if (dk.platform === 'cloudflare') {
    const parts = dk.key.split(':');
    const accountId = parts[0];
    providerId = 'custom:cloudflare';
    baseUrl = `https://api.cloudflare.com/client/v4/accounts/${accountId}/ai/v1`;
    actualKey = parts[1] || '';
  } else if (dk.platform === 'github') {
    continue; // Handled below
  } else if (mapping[dk.platform]) {
    providerId = mapping[dk.platform].id;
    baseUrl = mapping[dk.platform].base;
    actualKey = dk.key;
  } else {
    providerId = 'custom:' + dk.platform;
    baseUrl = '';
    actualKey = dk.key;
  }

  if (!authJson.credential_pool[providerId]) {
    authJson.credential_pool[providerId] = [];
  }
  
  // Check if it already exists to avoid duplicates
  const exists = authJson.credential_pool[providerId].some(c => c.access_token === actualKey);
  if (!exists) {
    authJson.credential_pool[providerId].push({
      id: generateUUID(),
      label: dk.platform + ' key',
      auth_type: 'api_key',
      priority: authJson.credential_pool[providerId].length,
      source: 'manual',
      access_token: actualKey,
      last_status: null,
      last_status_at: null,
      last_error_code: null,
      last_error_reason: null,
      last_error_message: null,
      last_error_reset_at: null,
      base_url: baseUrl,
      request_count: 0
    });
  }
}

fs.writeFileSync(authJsonPath, JSON.stringify(authJson, null, 2));
console.log('Updated auth.json with keys');

// 4. Update .env for GitHub
const githubKey = decryptedKeys.find(k => k.platform === 'github');
if (githubKey) {
  const envPath = path.join(process.env.HOME, '.hermes', '.env');
  let envContent = '';
  if (fs.existsSync(envPath)) {
    envContent = fs.readFileSync(envPath, 'utf8');
  }
  if (!envContent.includes('COPILOT_GITHUB_TOKEN=')) {
    envContent += `\nCOPILOT_GITHUB_TOKEN=${githubKey.key}\n`;
    fs.writeFileSync(envPath, envContent);
    console.log('Added COPILOT_GITHUB_TOKEN to .env');
  }
}

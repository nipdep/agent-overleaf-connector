// Credentials: environment first, then ~/.config/olmcp-overleaf/config.json (written with mode 0600).
import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';

export const configPath = () => process.env.OLMCP_OVERLEAF_CONFIG || join(homedir(), '.config', 'olmcp-overleaf', 'config.json');

export function loadConfig() {
  let file = {};
  try { if (existsSync(configPath())) file = JSON.parse(readFileSync(configPath(), 'utf-8')); } catch { /* unreadable: ignore */ }
  return {
    baseUrl: (process.env.OVERLEAF_BASE_URL || file.baseUrl || 'https://www.overleaf.com').replace(/\/+$/, ''),
    sessionCookie: process.env.OVERLEAF_SESSION || file.sessionCookie || '',
    cookieName: process.env.OVERLEAF_COOKIE_NAME || file.cookieName || 'overleaf_session2',
  };
}

export function saveConfig(values) {
  const merged = { ...JSON.parse(existsSync(configPath()) ? readFileSync(configPath(), 'utf-8') : '{}'), ...values };
  mkdirSync(dirname(configPath()), { recursive: true });
  writeFileSync(configPath(), JSON.stringify(merged, null, 2) + '\n', { mode: 0o600 });
  chmodSync(configPath(), 0o600);
}

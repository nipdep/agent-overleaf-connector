import { readFileSync } from 'node:fs';

// One source of truth: package.json.
export const VERSION = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf-8')).version;

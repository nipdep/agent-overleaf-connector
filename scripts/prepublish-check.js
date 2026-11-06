// Run by `npm publish` (prepublishOnly). npm 10 does not apply publishConfig.tag to a prerelease, so a plain
// `npm publish` of 1.0.0-alpha.N would become the `latest` version everyone installs by default. Refuse that.
import { readFileSync } from 'node:fs';

const { version } = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf-8'));
const tag = process.env.npm_config_tag || 'latest';
const prerelease = version.includes('-');
const label = prerelease ? version.split('-')[1].split('.')[0] : null;

if (prerelease && (tag === 'latest' || tag !== label)) {
  console.error(`Refusing to publish ${version} with tag "${tag}". Publish a prerelease under its own tag:\n  npm publish --tag ${label}`);
  process.exit(1);
}
if (!prerelease && tag !== 'latest') {
  console.error(`Refusing to publish the stable version ${version} under tag "${tag}". Use: npm publish`);
  process.exit(1);
}

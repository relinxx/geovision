import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(scriptDir, '..');

const viteConfig = readFileSync(resolve(frontendRoot, 'vite.config.ts'), 'utf8');
const authContext = readFileSync(resolve(frontendRoot, 'src/context/AuthContext.tsx'), 'utf8');
const apiClient = readFileSync(resolve(frontendRoot, 'src/utils/api.ts'), 'utf8');

const expectations = [
  {
    label: 'Vite dev server proxies auth requests to FastAPI',
    passed:
      /proxy\s*:/.test(viteConfig) &&
      /['"]\/auth['"]/.test(viteConfig) &&
      /target\s*:\s*['"]http:\/\/localhost:8000['"]/.test(viteConfig),
  },
  {
    label: 'Vite dev server proxies non-auth backend routes used by the app',
    passed:
      /['"]\/spatial['"]/.test(viteConfig) &&
      /['"]\/rag['"]/.test(viteConfig) &&
      /['"]\/copilot['"]/.test(viteConfig) &&
      /['"]\/risk['"]/.test(viteConfig),
  },
  {
    label: 'Auth requests prefer same-origin dev proxy before direct backend URL',
    passed:
      /IS_DEV/.test(authContext) &&
      /if\s*\(\s*IS_DEV\s*&&\s*origin\s*\)/.test(authContext) &&
      /pushCandidate\(origin\)[\s\S]*pushCandidate\(baseUrl\)/.test(authContext),
  },
  {
    label: 'API client requests prefer same-origin dev proxy before direct backend URL',
    passed:
      /IS_DEV/.test(apiClient) &&
      /if\s*\(\s*IS_DEV\s*&&\s*origin\s*\)/.test(apiClient) &&
      /pushCandidate\(origin\)[\s\S]*pushCandidate\(this\.baseUrl\)/.test(apiClient),
  },
];

const failed = expectations.filter((expectation) => !expectation.passed);

if (failed.length > 0) {
  for (const expectation of failed) {
    console.error(`FAIL: ${expectation.label}`);
  }
  process.exit(1);
}

for (const expectation of expectations) {
  console.log(`PASS: ${expectation.label}`);
}

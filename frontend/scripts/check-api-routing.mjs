import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(scriptDir, '..');

const authContext = readFileSync(
  resolve(frontendRoot, 'src/context/AuthContext.tsx'),
  'utf8'
);
const nginxConfig = readFileSync(resolve(frontendRoot, 'nginx.conf'), 'utf8');
const activeNginxConfig = nginxConfig
  .split('\n')
  .filter((line) => !line.trimStart().startsWith('#'))
  .join('\n');

const expectations = [
  {
    label: 'Auth requests include the frontend origin as a fallback base URL',
    passed:
      /window\.location(?:\?\.)?\.?origin/.test(authContext) &&
      /pushCandidate\(origin\)/.test(authContext),
  },
  {
    label: 'Nginx proxies auth requests to the backend Docker service',
    passed:
      /location\s+\/auth\/\s*\{/.test(activeNginxConfig) &&
      /proxy_pass\s+http:\/\/backend:8000/.test(activeNginxConfig),
  },
  {
    label: 'Nginx proxies API requests to the backend Docker service',
    passed:
      /location\s+\/api\/\s*\{/.test(activeNginxConfig) &&
      /proxy_pass\s+http:\/\/backend:8000/.test(activeNginxConfig),
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

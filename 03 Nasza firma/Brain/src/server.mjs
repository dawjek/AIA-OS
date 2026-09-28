import http from 'node:http';
import { realpathSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { buildSnapshot, searchSnapshot } from './content.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../..');
const PUBLIC = path.resolve(HERE, '../public');
const STATIC = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/index.html', ['index.html', 'text/html; charset=utf-8']],
  ['/kokpit', ['kokpit.html', 'text/html; charset=utf-8']],
  ['/kokpit.html', ['kokpit.html', 'text/html; charset=utf-8']],
  ['/map.css', ['map.css', 'text/css; charset=utf-8']],
  ['/map.js', ['map.js', 'text/javascript; charset=utf-8']],
  ['/graph.mjs', ['graph.mjs', 'text/javascript; charset=utf-8']],
  ['/kokpit.css', ['kokpit.css', 'text/css; charset=utf-8']],
  ['/kokpit.js', ['kokpit.js', 'text/javascript; charset=utf-8']],
  ['/shared.js', ['shared.js', 'text/javascript; charset=utf-8']],
  ['/favicon.svg', ['favicon.svg', 'image/svg+xml']],
]);

function response(res, status, body, type = 'application/json; charset=utf-8') {
  res.writeHead(status, {
    'Content-Type': type,
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
    'Content-Security-Policy': "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
  });
  res.end(body);
}

function json(res, status, value) {
  response(res, status, JSON.stringify(value));
}

function allowedHost(host) {
  return /^(?:localhost|127\.0\.0\.1|\[::1\])(?::\d{1,5})?$/.test(host || '');
}

export function createBrainServer({ root = ROOT, memoryProbe } = {}) {
  return http.createServer(async (req, res) => {
    if (!allowedHost(req.headers.host)) return json(res, 403, { error: 'Niedozwolony adres hosta.' });
    if (req.method !== 'GET') return json(res, 405, { error: 'Dozwolony jest tylko odczyt.' });
    let pathname;
    try { pathname = new URL(req.url, 'http://localhost').pathname; } catch { return json(res, 400, { error: 'Nieprawidłowy adres.' }); }
    try {
      if (STATIC.has(pathname)) {
        const [filename, type] = STATIC.get(pathname);
        return response(res, 200, await readFile(path.join(PUBLIC, filename)), type);
      }
      if (pathname === '/api/overview') {
        return json(res, 200, await buildSnapshot(root, { memoryProbe }));
      }
      if (pathname === '/api/search') {
        const query = new URL(req.url, 'http://localhost').searchParams.get('q') || '';
        const snapshot = await buildSnapshot(root, { memoryProbe });
        return json(res, 200, { results: searchSnapshot(snapshot, query) });
      }
      const documentRoute = pathname.match(/^\/api\/document\/([a-f0-9]{20})$/);
      if (documentRoute) {
        const snapshot = await buildSnapshot(root, { memoryProbe });
        const doc = snapshot.documents.find((item) => item.id === documentRoute[1]);
        if (!doc) return json(res, 404, { error: 'Nie znaleziono źródła.' });
        return json(res, 200, { ...doc, content: snapshot.contents.get(doc.id) });
      }
      return json(res, 404, { error: 'Nie znaleziono strony.' });
    } catch {
      return json(res, 500, { error: 'Nie udało się odczytać lokalnych źródeł.' });
    }
  });
}

function isMainModule() {
  if (!process.argv[1]) return false;
  try {
    return realpathSync(process.argv[1]).normalize('NFC') === realpathSync(fileURLToPath(import.meta.url)).normalize('NFC');
  } catch {
    return false;
  }
}

if (isMainModule()) {
  const requestedPort = Number(process.env.PORT || 4173);
  const port = Number.isInteger(requestedPort) && requestedPort >= 0 && requestedPort <= 65535 ? requestedPort : 4173;
  const server = createBrainServer();
  server.listen(port, '127.0.0.1', () => {
    const actualPort = server.address().port;
    process.stdout.write(`Brain: http://127.0.0.1:${actualPort}\n`);
  });
  server.on('error', (error) => {
    process.stderr.write(`Nie można uruchomić Braina: ${error.message}\n`);
    process.exitCode = 1;
  });
}

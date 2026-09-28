import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import { createBrainServer } from '../src/server.mjs';
import { layoutGraph, projectGraph, visibleGraph } from '../public/graph.mjs';

const DOCUMENTS = [
  { id: 'a', title: 'Start', section: 'Start', links: ['b'] },
  { id: 'b', title: 'Projekt', section: '01 Zarząd', links: ['c'] },
  { id: 'c', title: 'Wiedza', section: '05 Wiedza', links: [] },
];

test('Brain ma osobną pełnoekranową mapę i osobny kokpit', async () => {
  const server = createBrainServer();
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = 'http://127.0.0.1:' + server.address().port;
  try {
    const map = await fetch(base + '/');
    const cockpit = await fetch(base + '/kokpit');
    const graph = await fetch(base + '/graph.mjs');
    assert.equal(map.status, 200);
    assert.equal(cockpit.status, 200);
    assert.equal(graph.status, 200);
    assert.match(await map.text(), /id="graph-canvas"/);
    assert.match(await cockpit.text(), /id="cockpit-main"/);
    assert.match(await graph.text(), /function layoutGraph/);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test('mapa ma deterministyczny układ przestrzenny, obrót i filtr bez fałszywych połączeń', () => {
  const first = layoutGraph(DOCUMENTS);
  const second = layoutGraph(DOCUMENTS);
  assert.deepEqual(first, second);
  assert.equal(first.nodes.length, 3);
  assert.equal(first.edges.length, 2);
  assert.ok(first.nodes.some((node) => Math.abs(node.z) > 1));
  const front = projectGraph(first.nodes, { width: 900, height: 600, yaw: 0, pitch: 0, zoom: 1 });
  const turned = projectGraph(first.nodes, { width: 900, height: 600, yaw: 1, pitch: 0, zoom: 1 });
  assert.ok(front.some((node, index) => Math.abs(node.x - turned[index].x) > 5));
  const filtered = visibleGraph(first, '05 Wiedza');
  assert.deepEqual(filtered.nodes.map((node) => node.id), ['c']);
  assert.deepEqual(filtered.edges, []);
});

test('serwer startuje także przez bezwzględną ścieżkę z aliasem katalogu', { skip: process.platform === 'win32' }, async () => {
  const directory = await mkdtemp(path.join(tmpdir(), 'aia-brain-alias-'));
  const link = path.join(directory, 'alias.mjs');
  await symlink(fileURLToPath(new URL('../src/server.mjs', import.meta.url)), link);
  const child = spawn(process.execPath, [link], { env: { ...process.env, PORT: '0' } });
  let timer;
  try {
    const output = await Promise.race([
      new Promise((resolve, reject) => {
        child.stdout.once('data', (chunk) => resolve(chunk.toString()));
        child.once('exit', (code) => reject(new Error('Serwer zakończył pracę: ' + code)));
      }),
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Brak odpowiedzi serwera')), 3000); }),
    ]);
    clearTimeout(timer);
    assert.match(output, /Brain: http:\/\/127\.0\.0\.1:\d+/);
  } finally {
    clearTimeout(timer);
    if (child.exitCode === null && child.signalCode === null) {
      child.kill('SIGTERM');
      await new Promise((resolve) => child.once('exit', resolve));
    }
  }
});

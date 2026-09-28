import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';

import { buildSnapshot } from '../src/content.mjs';
import { createBrainServer } from '../src/server.mjs';

async function fixture() {
  const root = await mkdtemp(path.join(tmpdir(), 'aia-brain-test-'));
  const put = async (relative, content) => {
    const target = path.join(root, ...relative.split('/'));
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, content, 'utf8');
  };
  return { root, put };
}

test('pusta instalacja pokazuje rzeczywisty brak konfiguracji i następny krok', async () => {
  const { root } = await fixture();
  const snapshot = await buildSnapshot(root);

  assert.equal(snapshot.configured, false);
  assert.equal(snapshot.memory.state, 'empty');
  assert.equal(snapshot.documents.length, 0);
  assert.equal(snapshot.projects.length, 0);
  assert.match(snapshot.nextSteps[0], /START\.md|konfiguracj/i);
});

test('mapa łączy wybrane dokumenty i zapisane projekty bez wymyślania postępu', async () => {
  const { root, put } = await fixture();
  await put('03 Nasza firma/Brain/brain.config.json', JSON.stringify({
    system_name: 'Pracownia Anny',
    sources: ['01 Zarząd/PORTFOLIO.md'],
  }));
  await put('.ai/memory.json', JSON.stringify({ configured: true, sources: [{ path: '05 Wiedza/Kontekst/wlasciciel.md', required: true }], search_roots: [] }));
  await put('.ai/memory-projects.json', JSON.stringify({ projects: [{ id: 'p1', name: 'Ogród', root: '03 Nasza firma/Projekty własne/Ogród', state_path: '03 Nasza firma/Projekty własne/Ogród/STAN.md' }] }));
  await put('01 Zarząd/PORTFOLIO.md', '# Portfolio\n\n[Ogród](../03 Nasza firma/Projekty własne/Ogród/STAN.md)\n');
  await put('03 Nasza firma/Projekty własne/Ogród/STAN.md', '# Ogród\n\nNastępny krok: dobrać rośliny.\n');
  await put('05 Wiedza/Kontekst/wlasciciel.md', '# Anna\n\nProwadzę pracownię.\n');

  const snapshot = await buildSnapshot(root, { memoryProbe: async () => ({ status: 'ready' }) });
  const portfolio = snapshot.documents.find((doc) => doc.path === '01 Zarząd/PORTFOLIO.md');
  const projectState = snapshot.documents.find((doc) => doc.path.endsWith('Ogród/STAN.md'));

  assert.equal(snapshot.systemName, 'Pracownia Anny');
  assert.equal(snapshot.configured, true);
  assert.equal(snapshot.memory.state, 'ready');
  assert.equal(snapshot.projects.length, 1);
  assert.equal(snapshot.projects[0].name, 'Ogród');
  assert.equal(snapshot.projects[0].documentId, projectState.id);
  assert.deepEqual(portfolio.links, [projectState.id]);
  assert.equal(snapshot.projects[0].progress, undefined);
  assert.equal(snapshot.projects[0].nextStep, 'dobrać rośliny.');
  assert.match(snapshot.nextSteps[0], /dobrać rośliny/);
});

test('nie podąża za odsyłaczem poza starter i nie odczytuje dowiązania symbolicznego', async () => {
  const { root, put } = await fixture();
  await put('03 Nasza firma/Brain/brain.config.json', JSON.stringify({ sources: ['01 Zarząd/PORTFOLIO.md'], source_roots: ['05 Wiedza'] }));
  await put('01 Zarząd/PORTFOLIO.md', '# Źródła\n\n[poza](../../../../private.md)\n[tajne](../05 Wiedza/sekret.md)\n[szablon](../05 Wiedza/profil.template.md)\n');
  await put('private.md', 'tajna treść');
  await put('05 Wiedza/profil.template.md', '# To tylko szablon\n');
  await mkdir(path.join(root, '05 Wiedza'), { recursive: true });
  await symlink(path.join(root, 'private.md'), path.join(root, '05 Wiedza/sekret.md'));

  const snapshot = await buildSnapshot(root);

  assert.equal(snapshot.documents.length, 1);
  assert.deepEqual(snapshot.documents[0].links, []);
  assert.equal(JSON.stringify(snapshot).includes('tajna treść'), false);
});

test('API udostępnia tylko odkryty dokument; inne ścieżki odrzuca', async () => {
  const { root, put } = await fixture();
  await put('03 Nasza firma/Brain/brain.config.json', JSON.stringify({ sources: ['05 Wiedza/Kontekst/wlasciciel.md'] }));
  await put('05 Wiedza/Kontekst/wlasciciel.md', '# Anna\n\nProjektuję ogrody.\n');
  await put('sekret.md', 'nie pokazuj');
  const server = createBrainServer({ root });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const overview = await (await fetch(`${base}/api/overview`)).json();
    assert.equal(overview.documents.length, 1);
    const allowed = await fetch(`${base}/api/document/${overview.documents[0].id}`);
    assert.equal(allowed.status, 200);
    assert.match((await allowed.json()).content, /Projektuję ogrody/);

    const denied = await fetch(`${base}/api/document/${encodeURIComponent('../../sekret.md')}`);
    assert.equal(denied.status, 404);
    assert.equal((await fetch(`${base}/sekret.md`)).status, 404);
    assert.equal((await fetch(`${base}/api/document/no-such-id`)).status, 404);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test('wyszukiwanie zwraca fragment z prawdziwego źródła', async () => {
  const { root, put } = await fixture();
  await put('03 Nasza firma/Brain/brain.config.json', JSON.stringify({ sources: ['05 Wiedza/Wiki/notatka.md'] }));
  await put('05 Wiedza/Wiki/notatka.md', '# Notatka\n\nSpotkanie z Anną dotyczyło projektu ogrodu.\n');
  const server = createBrainServer({ root });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const response = await fetch(`${base}/api/search?q=AnNa`);
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.results.length, 1);
    assert.match(body.results[0].snippet, /Anną dotyczyło/);
    assert.equal(body.results[0].path, '05 Wiedza/Wiki/notatka.md');
    assert.equal(body.results[0].section, '05 Wiedza');
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test('siedem zapisanych decyzji pozostaje widoczne w API i prowadzi do dziennika', async () => {
  const { root, put } = await fixture();
  const entries = Array.from({ length: 7 }, (_, index) =>
    `## 2026-09-${String(index + 1).padStart(2, '0')} — Decyzja ${index + 1}\n\nTreść decyzji ${index + 1}.\n`).join('\n');
  await put('01 Zarząd/Decyzje/DZIENNIK.md', `# Dziennik decyzji\n\n${entries}`);
  const server = createBrainServer({ root });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const overview = await (await fetch(`${base}/api/overview`)).json();
    assert.equal(overview.decisions.length, 7);
    assert.deepEqual(overview.decisions.map((item) => item.title),
      Array.from({ length: 7 }, (_, index) => `2026-09-${String(index + 1).padStart(2, '0')} — Decyzja ${index + 1}`));
    const journal = overview.documents.find((doc) => doc.path === '01 Zarząd/Decyzje/DZIENNIK.md');
    assert.ok(overview.decisions.every((item) => item.documentId === journal.id));
    assert.equal((await fetch(`${base}/api/document/${journal.id}`)).status, 200);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test('duże puste drzewo zatrzymuje skan katalogów i oznacza niepełne pokrycie', async () => {
  const { root, put } = await fixture();
  await put('03 Nasza firma/Brain/brain.config.json', JSON.stringify({ source_roots: ['05 Wiedza'] }));
  const directory = path.join(root, '05 Wiedza');
  const names = Array.from({ length: 260 }, (_, index) => String(index).padStart(4, '0'));
  await Promise.all(names.map((name) => mkdir(path.join(directory, name), { recursive: true })));
  await put('05 Wiedza/0259/ukryty.md', '# Dokument poza budżetem\n');

  const snapshot = await buildSnapshot(root);

  assert.equal(snapshot.coverage.limited, true);
  assert.ok(snapshot.coverage.scannedDirectories <= 128);
  assert.ok(snapshot.coverage.scannedEntries <= 600);
  assert.equal(snapshot.documents.some((doc) => doc.title === 'Dokument poza budżetem'), false);
});

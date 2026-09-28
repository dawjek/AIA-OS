import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { lstat, readFile, readdir, realpath } from 'node:fs/promises';
import path from 'node:path';

const execFileAsync = promisify(execFile);
const SECTION_NAMES = new Set(['01 Zarząd', '02 Klienci', '03 Nasza firma', '04 Warsztat', '05 Wiedza']);
const CORE_SOURCES = [
  'START.md',
  '01 Zarząd/PORTFOLIO.md',
  '01 Zarząd/Decyzje/DZIENNIK.md',
  '05 Wiedza/Kontekst/wlasciciel.md',
  '05 Wiedza/Kontekst/firma.md',
  '05 Wiedza/Kontekst/priorytety.md',
  '05 Wiedza/Kontekst/mapa-pracy.md',
  '05 Wiedza/Kontekst/stan-rozmowy.md',
  '05 Wiedza/Wiki/INDEKS.md',
];
const MAX_DOCUMENTS = 180;
const MAX_DOC_BYTES = 256 * 1024;
const MAX_SCAN_DIRECTORIES = 128;
const MAX_SCAN_ENTRIES = 600;

function normalizedRelative(value, directory = false) {
  if (typeof value !== 'string' || !value || value.includes('\\') || value.includes('\0')) return null;
  const relative = path.posix.normalize(value.trim().replace(/^\.\//, ''));
  if (!relative || relative === '.' || relative === '..' || relative.startsWith('../') || relative.startsWith('/')) return null;
  const parts = relative.split('/');
  if (parts.some((part) => !part || part.startsWith('.'))) return null;
  if (relative !== 'START.md' && !SECTION_NAMES.has(parts[0])) return null;
  if (relative.startsWith('03 Nasza firma/Brain/')) return null;
  if (!directory && (path.posix.extname(relative).toLowerCase() !== '.md' || relative.endsWith('.template.md'))) return null;
  return relative;
}

async function isSafePath(root, relative, directory = false) {
  const clean = normalizedRelative(relative, directory);
  if (!clean) return false;
  const pieces = clean.split('/');
  let current = root;
  try {
    for (const piece of pieces) {
      current = path.join(current, piece);
      const stat = await lstat(current);
      if (stat.isSymbolicLink()) return false;
    }
    const finalStat = await lstat(current);
    if (directory ? !finalStat.isDirectory() : !finalStat.isFile() || finalStat.size > MAX_DOC_BYTES) return false;
    const actualRoot = await realpath(root);
    const actualPath = await realpath(current);
    return actualPath.startsWith(actualRoot + path.sep);
  } catch {
    return false;
  }
}

async function readKnownJson(root, relative) {
  const file = path.join(root, ...relative.split('/'));
  try {
    const stat = await lstat(file);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 64 * 1024) return null;
    return JSON.parse(await readFile(file, 'utf8'));
  } catch {
    return null;
  }
}

function sourcePath(item) {
  return typeof item === 'string' ? item : item && typeof item.path === 'string' ? item.path : null;
}

function markdownTargets(content, relative) {
  const targets = [];
  const pattern = /(?<!!)\[[^\]]*\]\((<[^>]+>|[^)]+)\)/g;
  for (const match of content.matchAll(pattern)) {
    let raw = match[1].trim();
    raw = raw.startsWith('<') && raw.endsWith('>') ? raw.slice(1, -1) : raw.replace(/\s+["'][^"']*["']$/, '');
    if (/^(?:[a-z][a-z\d+.-]*:|\/\/|#)/i.test(raw)) continue;
    try { raw = decodeURIComponent(raw.split('#')[0].split('?')[0]); } catch { continue; }
    const target = normalizedRelative(path.posix.join(path.posix.dirname(relative), raw));
    if (target) targets.push(target);
  }
  return [...new Set(targets)];
}

async function scanDirectory(root, relative, output, scan, depth = 0) {
  if (scan.stopped) return;
  if (depth > 6) { scan.limited = true; return; }
  if (output.size >= MAX_DOCUMENTS || scan.scannedDirectories >= MAX_SCAN_DIRECTORIES || scan.scannedEntries >= MAX_SCAN_ENTRIES) {
    scan.limited = true;
    scan.stopped = true;
    return;
  }
  if (!(await isSafePath(root, relative, true))) return;
  scan.scannedDirectories++;
  const absolute = path.join(root, ...relative.split('/'));
  let entries;
  try { entries = await readdir(absolute, { withFileTypes: true }); } catch { return; }
  entries.sort((a, b) => a.name.localeCompare(b.name, 'pl'));
  for (const entry of entries) {
    if (scan.stopped) break;
    if (output.size >= MAX_DOCUMENTS || scan.scannedEntries >= MAX_SCAN_ENTRIES) {
      scan.limited = true;
      scan.stopped = true;
      break;
    }
    scan.scannedEntries++;
    if (entry.name.startsWith('.') || entry.isSymbolicLink()) continue;
    const child = `${relative}/${entry.name}`;
    if (child === '03 Nasza firma/Brain') continue;
    if (entry.isDirectory()) await scanDirectory(root, child, output, scan, depth + 1);
    else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md') && !entry.name.endsWith('.template.md')) output.add(child);
  }
}

function plainExcerpt(content) {
  const candidate = content.split(/\r?\n/).map((line) => line.trim())
    .find((line) => line && !/^(?:#|<!--|\||```|---)/.test(line));
  return candidate ? candidate.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').slice(0, 190) : '';
}

function titleFor(relative, content) {
  const heading = content.match(/^#\s+(.+)$/m)?.[1]?.trim();
  return heading || path.posix.basename(relative, '.md').replace(/[-_]/g, ' ');
}

function decisionEntries(content, documentId) {
  const entries = [];
  const lines = content.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const heading = lines[i].match(/^#{2,4}\s+(.+)$/)?.[1]?.trim();
    if (!heading || !/\b\d{4}-\d{2}-\d{2}\b/.test(heading)) continue;
    const detail = lines.slice(i + 1).find((line) => line.trim() && !line.startsWith('#'))?.trim() || '';
    entries.push({ title: heading, detail: detail.slice(0, 220), documentId });
  }
  return entries;
}

export function searchSnapshot(snapshot, query) {
  const fold = (value) => value.toLocaleLowerCase('pl').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ł/g, 'l');
  const needle = fold(String(query || '').trim().slice(0, 100));
  if (!needle) return [];
  const results = [];
  for (const doc of snapshot.documents) {
    const content = snapshot.contents.get(doc.id) || '';
    const haystack = `${doc.title}\n${content}`;
    const index = fold(haystack).indexOf(needle);
    if (index < 0) continue;
    const start = Math.max(0, index - 60);
    const snippet = haystack.slice(start, Math.min(haystack.length, index + needle.length + 100))
      .replace(/[\r\n]+/g, ' ').trim();
    results.push({ id: doc.id, title: doc.title, path: doc.path, section: doc.section, snippet });
    if (results.length >= 20) break;
  }
  return results;
}

async function probeMemory(root) {
  const script = path.join(root, '90 Zaplecze techniczne', 'narzedzia', 'pamiec.py');
  try {
    const stat = await lstat(script);
    if (!stat.isFile() || stat.isSymbolicLink()) return null;
  } catch { return null; }
  const commands = process.platform === 'win32'
    ? [['py', '-3'], ['python']]
    : [['python3'], ['python']];
  for (const [command, ...prefix] of commands) {
    try {
      const { stdout } = await execFileAsync(command, [...prefix, script, '--root', root, 'status'], {
        cwd: root, timeout: 5000, maxBuffer: 128 * 1024, windowsHide: true,
      });
      return JSON.parse(stdout.trim());
    } catch (error) {
      if (error.code !== 'ENOENT') return null;
    }
  }
  return null;
}

function memoryView(config, probe) {
  if (!config || config.configured !== true) return { state: 'empty', label: 'Do konfiguracji', detail: 'Pamięć nie została jeszcze skonfigurowana.' };
  const states = {
    ready: ['ready', 'Pakiet gotowy', 'Stan plików został sprawdzony. Użycie pamięci w nowej rozmowie wymaga osobnej próby.'],
    stale: ['stale', 'Wymaga odświeżenia', 'Źródła lub pakiet pamięci wymagają ponownego zbudowania.'],
    empty: ['empty', 'Brak pakietu', 'Konfiguracja istnieje, ale pakiet nie zawiera jeszcze zapisanych źródeł.'],
    unavailable: ['unavailable', 'Brak odczytu', 'Nie udało się potwierdzić stanu pamięci.'],
  };
  const [state, label, detail] = states[probe?.status] || states.unavailable;
  return { state, label, detail, revision: typeof probe?.revision === 'string' ? probe.revision : null };
}

export async function buildSnapshot(root, { memoryProbe = probeMemory } = {}) {
  const brain = await readKnownJson(root, '03 Nasza firma/Brain/brain.config.json') || {};
  const memoryConfig = await readKnownJson(root, '.ai/memory.json');
  const projectConfig = await readKnownJson(root, '.ai/memory-projects.json');
  const configured = memoryConfig?.configured === true || brain.configured === true;
  const selected = new Set(CORE_SOURCES);
  for (const item of [...(Array.isArray(brain.sources) ? brain.sources : []), ...(Array.isArray(memoryConfig?.sources) ? memoryConfig.sources : [])]) {
    const relative = normalizedRelative(sourcePath(item));
    if (relative) selected.add(relative);
  }
  const projectItems = Array.isArray(projectConfig?.projects) ? projectConfig.projects : [];
  for (const project of projectItems) {
    const state = normalizedRelative(project?.state_path);
    if (state) selected.add(state);
  }
  const roots = new Set([...(Array.isArray(brain.source_roots) ? brain.source_roots : []),
    ...(configured && Array.isArray(memoryConfig?.search_roots) ? memoryConfig.search_roots : [])]);
  const scan = { limited: false, stopped: false, scannedDirectories: 0, scannedEntries: 0 };
  for (const value of roots) {
    if (scan.stopped) break;
    const relative = normalizedRelative(value, true);
    if (relative && relative !== 'START.md') await scanDirectory(root, relative, selected, scan);
  }

  const documents = [];
  const contents = new Map();
  const pending = [...selected];
  const visited = new Set();
  while (pending.length && documents.length < MAX_DOCUMENTS) {
    const relative = pending.shift();
    if (visited.has(relative)) continue;
    visited.add(relative);
    if (!(await isSafePath(root, relative))) continue;
    let content;
    try { content = await readFile(path.join(root, ...relative.split('/')), 'utf8'); } catch { continue; }
    const id = createHash('sha256').update(relative).digest('hex').slice(0, 20);
    const doc = {
      id,
      path: relative,
      title: titleFor(relative, content),
      section: relative === 'START.md' ? 'Start' : relative.split('/')[0],
      excerpt: plainExcerpt(content),
      links: [],
    };
    documents.push(doc);
    contents.set(id, content);
    for (const target of markdownTargets(content, relative)) if (!visited.has(target)) pending.push(target);
  }
  if (pending.length) scan.limited = true;
  const byPath = new Map(documents.map((doc) => [doc.path, doc]));
  for (const doc of documents) doc.links = markdownTargets(contents.get(doc.id), doc.path)
    .map((target) => byPath.get(target)?.id).filter(Boolean);

  const projects = projectItems.filter((project) => project && typeof project.name === 'string' && project.name.trim())
    .map((project) => {
      const documentId = byPath.get(normalizedRelative(project.state_path))?.id || null;
      const content = documentId ? contents.get(documentId) : '';
      const nextStep = content.match(/^\s*(?:[-*]\s*)?(?:\*\*)?Następny krok(?:\*\*)?\s*:\s*(.+)$/mi)?.[1]?.trim();
      return {
        id: String(project.id || '').slice(0, 80),
        name: project.name.trim().slice(0, 120),
        root: typeof project.root === 'string' ? project.root : '',
        documentId,
        ...(nextStep ? { nextStep: nextStep.slice(0, 220) } : {}),
      };
    });
  const decisionDoc = byPath.get('01 Zarząd/Decyzje/DZIENNIK.md');
  const decisions = decisionDoc ? decisionEntries(contents.get(decisionDoc.id), decisionDoc.id) : [];
  const rawAreas = Array.isArray(brain.areas) ? brain.areas : [];
  const areas = rawAreas.map((area) => typeof area === 'string' ? area : area?.name)
    .filter((area) => typeof area === 'string' && area.trim()).map((area) => area.trim().slice(0, 80));
  const memory = memoryView(memoryConfig, configured ? await memoryProbe(root) : null);
  const nextSteps = [];
  for (const project of projects.filter((item) => item.nextStep).slice(0, 3)) nextSteps.push(`${project.name}: ${project.nextStep}`);
  if (!configured) nextSteps.push('Otwórz START.md i poproś AI o przeprowadzenie pierwszej konfiguracji.');
  if (configured && !projects.length) nextSteps.push('Dodaj pierwszy projekt i jego źródło do portfolio.');
  if (configured && !decisions.length) nextSteps.push('Zapisz pierwszą decyzję w dzienniku.');
  if (configured && memory.state !== 'ready') nextSteps.push('Sprawdź i zbuduj pakiet pamięci według instrukcji startowej.');
  const snapshot = {
    systemName: typeof brain.system_name === 'string' && brain.system_name.trim() ? brain.system_name.trim().slice(0, 120) : 'Mój system pracy',
    configured,
    areas,
    projects,
    decisions,
    memory,
    documents,
    nextSteps,
    coverage: {
      limited: scan.limited,
      scannedDirectories: scan.scannedDirectories,
      scannedEntries: scan.scannedEntries,
    },
  };
  Object.defineProperty(snapshot, 'contents', { value: contents });
  return snapshot;
}

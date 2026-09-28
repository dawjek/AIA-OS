import { layoutGraph, projectGraph, visibleGraph } from './graph.mjs';
import { getJSON, renderMarkdown } from './shared.js';

const $ = (selector) => document.querySelector(selector);
const canvas = $('#graph-canvas');
const context = canvas.getContext('2d');
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const palette = {
  Start: '#43b9b8',
  '01 Zarząd': '#8e78d2',
  '02 Klienci': '#dc809d',
  '03 Nasza firma': '#46b494',
  '04 Warsztat': '#e7ae5f',
  '05 Wiedza': '#5a9ce3',
};
const state = {
  data: null, graph: { nodes: [], edges: [], sections: [] }, section: null,
  yaw: .35, pitch: -.18, zoom: 1, rotating: !reduceMotion.matches,
  width: 0, height: 0, projected: [], frame: 0, drag: null,
  pointers: new Map(), pinch: 0, hover: null, replayStart: 0,
};

function sectionColor(section) { return palette[section] || '#78a0d0'; }
function plural(count, one, few, many) {
  if (count === 1) return one;
  if (count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 12 || count % 100 > 14)) return few;
  return many;
}
function safeText(selector, value) { $(selector).textContent = String(value); }
function setError(message) { safeText('#error-banner', message); $('#error-banner').hidden = false; }
function schedule() {
  if (!state.frame && document.visibilityState !== 'hidden') state.frame = requestAnimationFrame(draw);
}

function sizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  state.width = rect.width;
  state.height = rect.height;
  canvas.width = Math.max(1, Math.round(rect.width * ratio));
  canvas.height = Math.max(1, Math.round(rect.height * ratio));
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  schedule();
}

function orbitRing(radiusX, radiusY, yaw, alpha) {
  const centerX = state.width < 700 ? state.width * .5 : state.width * .55;
  const centerY = state.height * .52;
  context.beginPath();
  context.ellipse(centerX, centerY, radiusX, radiusY, yaw, 0, Math.PI * 2);
  context.strokeStyle = 'rgba(88,126,178,' + alpha + ')';
  context.lineWidth = 1;
  context.stroke();
}

function draw(now) {
  state.frame = 0;
  const width = state.width;
  const height = state.height;
  if (!width || !height) return;
  if (state.rotating && !state.drag && !reduceMotion.matches) state.yaw += .0014;
  context.clearRect(0, 0, width, height);
  orbitRing(Math.min(width * .23, 330), Math.min(height * .24, 200), state.yaw * .13, .18);
  orbitRing(Math.min(width * .29, 420), Math.min(height * .3, 260), -.3 + state.y * .08, .12);
  orbitRing(Math.min(width * .35, 510), Math.min(height * .38, 320), .34 + state.y * .05, .07);

  const graph = visibleGraph(state.graph, state.section);
  let count = graph.nodes.length;
  if (state.replayStart && !reduceMotion.matches) {
    const progress = Math.min(1, (now - state.replayStart) / 4600);
    count = Math.max(1, Math.ceil(graph.nodes.length * progress));
    if (progress >= 1) state.replayStart = 0;
  }
  const nodes = graph.nodes.slice(0, count);
  const projected = projectGraph(nodes, state);
  state.projected = projected;
  const byId = new Map(projected.map((item) => [item.id, item]));
  const edges = graph.edges.filter((edge) => byId.has(edge.source) && byId.has(edge.target));
  for (const edge of edges) {
    const a = byId.get(edge.source);
    const b = byId.get(edge.target);
    context.beginPath();
    context.moveTo(a.x, a.y);
    context.lineTo(b.x, b.y);
    context.strokeStyle = 'rgba(69,108,163,.3)';
    context.lineWidth = .7 + Math.min(a.scale, b.scale) * .4;
    context.stroke();
  }
  const ordered = [...projected].sort((a, b) => a.depth - b.depth);
  for (const node of ordered) {
    const color = sectionColor(node.section);
    const hover = node.id === state.hover;
    const radius = node.radius * (hover ? 1.4 : 1);
    const glow = context.createRadialGradient(node.x, node.y, 0, node.x, node.y, radius * 5);
    glow.addColorStop(0, color + '6b');
    glow.addColorStop(1, color + '00');
    context.fillStyle = glow;
    context.beginPath();
    context.arc(node.x, node.y, radius * 5, 0, Math.PI * 2);
    context.fill();
    context.beginPath();
    context.arc(node.x, node.y, radius, 0, Math.PI * 2);
    context.fillStyle = color;
    context.fill();
    context.lineWidth = Math.max(1, radius * .22);
    context.strokeStyle = 'rgba(255,255,255,.92)';
    context.stroke();
    if ((node.degree > 1 || hover || projected.length <= 12) && width > 700) {
      context.font = '600 11px "Avenir Next","Segoe UI",sans-serif';
      context.textAlign = 'left';
      context.fillStyle = '#2f4a6d';
      context.shadowColor = '#f7fbff';
      context.shadowBlur = 4;
      context.fillText(node.title.slice(0, 34), node.x + radius + 7, node.y + 4);
      context.shadowBlur = 0;
    }
  }
  safeText('#visible-status', projected.length + ' ' + plural(projected.length, 'dokument', 'dokumenty', 'dokumentów')
    + ' · ' + edges.length + ' ' + plural(edges.length, 'połączenie', 'połączenia', 'połączeń'));
  if (state.rotating || state.replayStart) schedule();
}

function hitTest(x, y) {
  return [...state.projected].reverse().find((node) => Math.hypot(x - node.x, y - node.y) <= Math.max(14, node.radius + 7));
}

function renderFilters() {
  const list = $('#filter-list');
  list.replaceChildren();
  const counts = new Map();
  for (const node of state.graph.nodes) counts.set(node.section, (counts.get(node.section) || 0) + 1);
  const options = [null, ...state.graph.sections];
  for (const section of options) {
    const button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('aria-pressed', String(section === state.section));
    const label = document.createElement('span');
    const dot = document.createElement('i');
    dot.style.setProperty('--swatch', section ? sectionColor(section) : '#7896bd');
    label.append(dot, document.createTextNode(section || 'Wszystkie'));
    const count = document.createElement('b');
    count.textContent = section ? counts.get(section) || 0 : state.graph.nodes.length;
    button.append(label, count);
    button.addEventListener('click', () => {
      state.section = section;
      state.replayStart = 0;
      renderFilters();
      schedule();
    });
    list.append(button);
  }
  safeText('#filter-count', state.graph.sections.length);
}

function renderInventory() {
  const data = state.data;
  const list = $('#inventory-sections');
  list.replaceChildren();
  const grouped = new Map();
  for (const doc of data.documents) grouped.set(doc.section, (grouped.get(doc.section) || 0) + 1);
  for (const [section, count] of grouped) {
    const button = document.createElement('button');
    button.type = 'button';
    const label = document.createElement('strong');
    label.textContent = section;
    const total = document.createElement('span');
    total.textContent = count + ' dokumentów';
    button.append(label, total);
    button.addEventListener('click', () => {
      state.section = section;
      renderFilters();
      toggleInventory(false);
      schedule();
    });
    list.append(button);
  }
  safeText('#inventory-lead', data.documents.length + ' ' + plural(data.documents.length, 'dokument', 'dokumenty', 'dokumentów')
    + ' i ' + state.graph.edges.length + ' ' + plural(state.graph.edges.length, 'połączenie', 'połączenia', 'połączeń') + ' z wybranych plików.');
  safeText('#inventory-note', data.coverage?.limited
    ? 'Skan został ograniczony. Te liczby mogą nie obejmować wszystkich zapisanych źródeł.'
    : 'Połączenia pochodzą z odsyłaczy Markdown. Brak linii nie oznacza braku wiedzy.');
}

function toggleInventory(open) {
  $('#inventory').hidden = !open;
  $('#inventory-toggle').setAttribute('aria-expanded', String(open));
  if (open) { $('#source-drawer').hidden = true; $('#inventory-close').focus(); }
}

function toggleCinema() {
  const enabled = $('#mapa').classList.toggle('cinema');
  $('#cinema-toggle').setAttribute('aria-pressed', String(enabled));
  if (enabled) {
    toggleInventory(false);
    $('#source-drawer').hidden = true;
  }
  canvas.focus();
}

async function openDocument(id) {
  try {
    const source = await getJSON('/api/document/' + encodeURIComponent(id));
    $('#inventory').hidden = true;
    $('#inventory-toggle').setAttribute('aria-expanded', 'false');
    safeText('#source-section', source.section);
    safeText('#source-title', source.title);
    safeText('#source-path', source.path);
    renderMarkdown($('#source-content'), source.content);
    const links = $('#source-links');
    links.replaceChildren();
    for (const linked of source.links || []) {
      const target = state.data.documents.find((item) => item.id === linked);
      if (!target) continue;
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = target.title + ' ↗';
      button.addEventListener('click', () => openDocument(target.id));
      links.append(button);
    }
    $('#source-drawer').hidden = false;
    $('#source-close').focus();
  } catch (error) { setError(error.message); }
}

let searchTimer = 0;
let searchNumber = 0;
async function search() {
  const query = $('#search-input').value.trim();
  const box = $('#search-results');
  const current = ++searchNumber;
  if (!query) { box.hidden = true; box.replaceChildren(); return; }
  try {
    const data = await getJSON('/api/search?q=' + encodeURIComponent(query));
    if (current !== searchNumber) return;
    box.replaceChildren();
    for (const result of data.results) {
      const button = document.createElement('button');
      button.type = 'button';
      const title = document.createElement('strong');
      title.textContent = result.title;
      const detail = document.createElement('span');
      detail.textContent = result.snippet || result.path;
      button.append(title, detail);
      button.addEventListener('click', () => {
        state.section = null;
        renderFilters();
        box.hidden = true;
        openDocument(result.id);
        schedule();
      });
      box.append(button);
    }
    if (!data.results.length) {
      const empty = document.createElement('p');
      empty.textContent = 'Brak wyników w wybranych źródłach.';
      box.append(empty);
    }
    box.hidden = false;
  } catch (error) { setError(error.message); }
}

function bindControls() {
  $('#inventory-toggle').addEventListener('click', () => toggleInventory($('#inventory').hidden));
  $('#inventory-close').addEventListener('click', () => toggleInventory(false));
  $('#source-close').addEventListener('click', () => { $('#source-drawer').hidden = true; canvas.focus(); });
  $('#rotate-toggle').addEventListener('click', () => {
    state.rotating = !state.rotating;
    $('#rotate-toggle').setAttribute('aria-pressed', String(state.rotating));
    $('#rotate-toggle').setAttribute('aria-label', state.rotating ? 'Wstrzymaj obrót mapy' : 'Wznów obrót mapy');
    schedule();
  });
  $('#reset-view').addEventListener('click', () => {
    state.yaw = .35; state.pitch = -.18; state.zoom = 1; state.section = null; state.replayStart = 0;
    renderFilters(); schedule();
  });
  $('#replay').addEventListener('click', () => {
    state.replayStart = reduceMotion.matches ? 0 : performance.now();
    schedule();
  });
  $('#cinema-toggle').addEventListener('click', toggleCinema);
  $('#open-start').addEventListener('click', () => {
    const start = state.data?.documents.find((doc) => doc.path === 'START.md');
    if (start) openDocument(start.id);
  });
  $('#search-form').addEventListener('submit', (event) => { event.preventDefault(); clearTimeout(searchTimer); search(); });
  $('#search-input').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(search, 190); });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      $('#source-drawer').hidden = true; toggleInventory(false); $('#search-results').hidden = true;
      return;
    }
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
    if (event.key === '/') {
      event.preventDefault(); $('#search-input').focus();
    }
    if (event.key.toLowerCase() === 'c') { event.preventDefault(); toggleCinema(); }
    if (event.key.toLowerCase() === 'd') { event.preventDefault(); $('#replay').click(); }
  });
  canvas.addEventListener('keydown', (event) => {
    const changes = { ArrowLeft: [-.15, 0], ArrowRight: [.15, 0], ArrowUp: [0, -.12], ArrowDown: [0, .12] };
    if (changes[event.key]) {
      event.preventDefault();
      state.yaw += changes[event.key][0];
      state.pitch = Math.max(-1.15, Math.min(1.15, state.pitch + changes[event.key][1]));
      schedule();
    }
    if (event.key === '+' || event.key === '=') { event.preventDefault(); state.zoom = Math.min(2.4, state.zoom * 1.12); schedule(); }
    if (event.key === '-') { event.preventDefault(); state.zoom = Math.max(.45, state.zoom / 1.12); schedule(); }
    if (event.key === 'Enter' && state.projected[0]) { event.preventDefault(); openDocument(state.projected[0].id); }
  });
  canvas.addEventListener('pointerdown', (event) => {
    canvas.setPointerCapture(event.pointerId);
    state.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    state.drag = { x: event.clientX, y: event.clientY, moved: false };
    state.pinch = 0;
  });
  canvas.addEventListener('pointermove', (event) => {
    const bounds = canvas.getBoundingClientRect();
    if (!state.pointers.has(event.pointerId)) {
      const node = hitTest(event.clientX - bounds.left, event.clientY - bounds.top);
      if (node?.id !== state.hover) { state.hover = node?.id || null; schedule(); }
      canvas.style.cursor = node ? 'pointer' : 'grab';
      return;
    }
    const previous = state.pointers.get(event.pointerId);
    state.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (state.pointers.size === 2) {
      const points = [...state.pointers.values()];
      const distance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
      if (state.pinch) state.zoom = Math.max(.45, Math.min(2.4, state.zoom * distance / state.pinch));
      state.pinch = distance;
      state.drag.moved = true;
    } else {
      const dx = event.clientX - previous.x;
      const dy = event.clientY - previous.y;
      state.yaw += dx * .006;
      state.pitch = Math.max(-1.15, Math.min(1.15, state.pitch + dy * .005));
      if (Math.hypot(event.clientX - state.drag.x, event.clientY - state.drag.y) > 5) state.drag.moved = true;
    }
    schedule();
  });
  const endPointer = (event) => {
    const click = state.drag && !state.drag.moved && state.pointers.size === 1;
    state.pointers.delete(event.pointerId);
    if (click) {
      const bounds = canvas.getBoundingClientRect();
      const node = hitTest(event.clientX - bounds.left, event.clientY - bounds.top);
      if (node) openDocument(node.id);
    }
    if (!state.pointers.size) { state.drag = null; state.pinch = 0; }
  };
  canvas.addEventListener('pointerup', endPointer);
  canvas.addEventListener('pointercancel', endPointer);
  canvas.addEventListener('wheel', (event) => {
    event.preventDefault();
    state.zoom = Math.max(.45, Math.min(2.4, state.zoom * (event.deltaY > 0 ? .91 : 1.09)));
    schedule();
  }, { passive: false });
  window.addEventListener('resize', sizeCanvas);
  document.addEventListener('visibilitychange', schedule);
  reduceMotion.addEventListener('change', () => {
    if (reduceMotion.matches) { state.rotating = false; state.replayStart = 0; $('#rotate-toggle').setAttribute('aria-pressed', 'false'); }
    schedule();
  });
}

async function start() {
  bindControls();
  $('#rotate-toggle').setAttribute('aria-pressed', String(state.rotating));
  $('#rotate-toggle').setAttribute('aria-label', state.rotating ? 'Wstrzymaj obrót mapy' : 'Wznów obrót mapy');
  sizeCanvas();
  try {
    const data = await getJSON('/api/overview');
    state.data = data;
    state.graph = layoutGraph(data.documents);
    document.title = data.systemName + ' · Mapa wiedzy';
    safeText('#map-title', 'Wiedza w jednym obrazie.');
    safeText('#stat-documents', data.documents.length);
    safeText('#stat-areas', state.graph.sections.length);
    safeText('#stat-links', state.graph.edges.length);
    $('#setup-panel').hidden = data.configured;
    const startDocument = data.documents.find((doc) => doc.path === 'START.md');
    $('#open-start').disabled = !startDocument;
    $('#coverage-warning').hidden = !data.coverage?.limited;
    renderFilters();
    renderInventory();
    schedule();
    const requested = new URLSearchParams(location.search).get('doc');
    if (requested && data.documents.some((doc) => doc.id === requested)) openDocument(requested);
  } catch (error) { setError(error.message); }
}

start();

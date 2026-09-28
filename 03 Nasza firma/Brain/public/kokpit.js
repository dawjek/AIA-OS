import { layoutGraph } from './graph.mjs';
import { getJSON, renderMarkdown } from './shared.js';

const $ = (selector) => document.querySelector(selector);
let overview = null;
let searchNumber = 0;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

function emptyCard(title, detail) {
  const card = element('div', 'empty-card');
  card.append(element('strong', '', title), element('p', '', detail));
  return card;
}

async function openDocument(id) {
  try {
    const source = await getJSON('/api/document/' + encodeURIComponent(id));
    $('#document-title').textContent = source.title;
    $('#document-path').textContent = source.path;
    $('#map-return').href = '/?doc=' + encodeURIComponent(source.id);
    renderMarkdown($('#document-content'), source.content);
    const links = $('#document-links');
    links.replaceChildren();
    for (const linked of source.links || []) {
      const doc = overview.documents.find((item) => item.id === linked);
      if (!doc) continue;
      const button = element('button', '', doc.title + ' ↗');
      button.type = 'button';
      button.addEventListener('click', () => openDocument(doc.id));
      links.append(button);
    }
    if (!$('#document-dialog').open) $('#document-dialog').showModal();
  } catch (error) {
    $('#error-banner').textContent = error.message;
    $('#error-banner').hidden = false;
  }
}

function documentCard(doc, snippet = doc.excerpt) {
  const card = element('button', 'document-card');
  card.type = 'button';
  card.addEventListener('click', () => openDocument(doc.id));
  card.append(element('span', 'card-kicker', doc.section), element('strong', '', doc.title),
    element('p', '', snippet || 'Otwórz dokument, aby przeczytać źródło.'),
    element('small', '', doc.path), element('span', 'card-arrow', '↗'));
  return card;
}

function renderDocuments(rows, searched = false) {
  const list = $('#documents-list');
  list.replaceChildren();
  if (!rows.length) list.append(emptyCard(searched ? 'Brak wyników' : 'Brak dokumentów', searched
    ? 'Spróbuj innego hasła.' : 'Źródła pojawią się po konfiguracji.'));
  else for (const doc of rows) list.append(documentCard(doc, doc.snippet || doc.excerpt));
  $('#search-summary').textContent = searched
    ? 'Pokazano do 20 wyników: ' + rows.length + (overview.coverage?.limited ? '. Skan źródeł jest ograniczony.' : '.')
    : 'Wybrane dokumenty: ' + rows.length + (overview.coverage?.limited ? '. Skan źródeł jest ograniczony.' : '.');
}

function renderProjects(data) {
  const list = $('#projects-list');
  list.replaceChildren();
  if (!data.projects.length) {
    list.append(emptyCard('Nie dodano jeszcze projektu', 'Podłącz pierwszy projekt podczas konfiguracji. Jego stan i następny krok pojawią się tutaj.'));
    return;
  }
  for (const project of data.projects) {
    const card = element(project.documentId ? 'button' : 'article', 'project-card');
    if (project.documentId) {
      card.type = 'button';
      card.addEventListener('click', () => openDocument(project.documentId));
    }
    card.append(element('span', 'card-kicker', 'PROJEKT'), element('strong', '', project.name),
      element('p', '', project.nextStep ? 'Następny krok: ' + project.nextStep : 'Brak zapisanego następnego kroku.'),
      element('small', '', project.documentId ? 'Źródło jest podłączone' : 'Brak podłączonego stanu'),
      element('span', 'card-arrow', '↗'));
    list.append(card);
  }
}

function renderDecisions(data) {
  const list = $('#decisions-list');
  list.replaceChildren();
  if (!data.decisions.length) {
    list.append(emptyCard('Nie zapisano jeszcze decyzji', 'Decyzje wpisane do dziennika z datą pojawią się tutaj.'));
    return;
  }
  data.decisions.forEach((decision, index) => {
    const row = element('button', 'decision-row');
    row.type = 'button';
    row.addEventListener('click', () => openDocument(decision.documentId));
    row.append(element('span', 'row-number', String(index + 1).padStart(2, '0')));
    const detail = element('span', 'row-detail');
    detail.append(element('strong', '', decision.title), element('small', '', decision.detail));
    row.append(detail, element('span', 'row-arrow', '↗'));
    list.append(row);
  });
}

function render(data) {
  overview = data;
  const graph = layoutGraph(data.documents);
  $('#system-title').replaceChildren(document.createTextNode(data.systemName));
  document.title = data.systemName + ' · Kokpit';
  $('#setup-panel').hidden = data.configured;
  const start = data.documents.find((doc) => doc.path === 'START.md');
  $('#open-start').disabled = !start;
  $('#open-start').onclick = start ? () => openDocument(start.id) : null;
  $('#document-count').textContent = data.documents.length;
  $('#link-count').textContent = graph.edges.length;
  $('#project-count').textContent = data.projects.length;
  $('#area-count').textContent = graph.sections.length;
  $('#document-detail').textContent = data.coverage?.limited ? 'pokazane; skan ograniczony' : 'wybrane źródła';
  $('#memory-label').textContent = data.memory.label;
  $('#memory-detail').textContent = data.memory.detail;
  $('#memory-state').textContent = data.memory.state === 'ready' ? 'GOTOWY' : data.memory.state === 'empty' ? 'START' : 'SPRAWDŹ';
  $('#memory-state').dataset.state = data.memory.state;

  const steps = $('#next-steps');
  steps.replaceChildren();
  const next = data.nextSteps.length ? data.nextSteps : ['Nie ma zapisanego następnego kroku. Po wykonaniu pracy uzupełnij stan projektu.'];
  for (const step of next) steps.append(element('li', '', step));
  const areas = $('#areas-list');
  areas.replaceChildren();
  if (data.areas.length) {
    for (const area of data.areas) areas.append(element('span', 'area-pill', area));
  } else areas.append(emptyCard('Obszary nie są jeszcze wybrane', 'Dodasz je podczas konfiguracji systemu.'));
  renderProjects(data);
  renderDecisions(data);
  renderDocuments(data.documents);
  $('#read-state').textContent = 'Odczyt z lokalnych plików';
}

async function load() {
  $('#read-state').textContent = 'Odczytuję źródła…';
  try {
    const data = await getJSON('/api/overview');
    render(data);
    $('#error-banner').hidden = true;
  } catch (error) {
    $('#read-state').textContent = overview ? 'Ostatni udany odczyt' : 'Brak odczytu';
    $('#error-banner').textContent = error.message + (overview ? ' Pokazujemy ostatnio odczytane dane.' : '');
    $('#error-banner').hidden = false;
  }
}

async function search() {
  const query = $('#search-input').value.trim();
  const current = ++searchNumber;
  if (!query) { if (overview) renderDocuments(overview.documents); return; }
  try {
    const result = await getJSON('/api/search?q=' + encodeURIComponent(query));
    if (current === searchNumber) renderDocuments(result.results, true);
  } catch (error) {
    $('#error-banner').textContent = error.message;
    $('#error-banner').hidden = false;
  }
}

$('#today').textContent = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date());
$('#refresh').addEventListener('click', load);
$('#close-dialog').addEventListener('click', () => $('#document-dialog').close());
$('#search-form').addEventListener('submit', (event) => { event.preventDefault(); search(); });
$('#search-input').addEventListener('input', search);
document.addEventListener('keydown', (event) => {
  if (event.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
    event.preventDefault(); $('#search-input').focus();
  }
});
setInterval(() => { if (document.visibilityState === 'visible' && !$('#document-dialog').open) load(); }, 30000);
load();

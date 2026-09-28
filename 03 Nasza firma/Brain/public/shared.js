export async function getJSON(url) {
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error('Odczyt nie powiódł się (' + response.status + ').');
  return response.json();
}

function plain(value) {
  return value.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/(?:\*\*|__)(.*?)(?:\*\*|__)/g, '$1')
    .replace(/\`/g, '');
}

export function renderMarkdown(container, markdown) {
  container.replaceChildren();
  const lines = String(markdown || '').split(/\r?\n/);
  let paragraph = [];
  let list = null;
  let code = [];
  let inCode = false;
  const flushParagraph = () => {
    if (!paragraph.length) return;
    const element = document.createElement('p');
    element.textContent = plain(paragraph.join(' '));
    container.append(element);
    paragraph = [];
  };
  const flushList = () => { list = null; };
  for (const line of lines) {
    if (line.trim().startsWith('\`\`\`')) {
      flushParagraph();
      flushList();
      if (inCode) {
        const pre = document.createElement('pre');
        pre.textContent = code.join('\n');
        container.append(pre);
        code = [];
      }
      inCode = !inCode;
      continue;
    }
    if (inCode) { code.push(line); continue; }
    if (!line.trim()) { flushParagraph(); flushList(); continue; }
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      const element = document.createElement(heading[1].length < 3 ? 'h3' : 'h4');
      element.textContent = plain(heading[2]);
      container.append(element);
      continue;
    }
    const item = line.match(/^\s*[-*]\s+(.+)$/);
    if (item) {
      flushParagraph();
      if (!list) {
        list = document.createElement('ul');
        container.append(list);
      }
      const element = document.createElement('li');
      element.textContent = plain(item[1]);
      list.append(element);
      continue;
    }
    flushList();
    paragraph.push(line.trim());
  }
  flushParagraph();
  if (inCode && code.length) {
    const pre = document.createElement('pre');
    pre.textContent = code.join('\n');
    container.append(pre);
  }
}

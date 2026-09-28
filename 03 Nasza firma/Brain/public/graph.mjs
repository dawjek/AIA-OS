// Przestrzenny układ dokumentów i projekcja kamery. Bez zależności od DOM.
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

function fraction(value) {
  let hash = 2166136261;
  for (const character of String(value)) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) / 4294967295;
}

export function layoutGraph(documents) {
  const sections = [...new Set(documents.map((item) => item.section))].sort((a, b) => a.localeCompare(b, 'pl'));
  const sectionIndex = new Map(sections.map((item, index) => [item, index]));
  const groupedIndex = new Map();
  const degree = new Map(documents.map((item) => [item.id, item.links?.length || 0]));
  for (const document of documents) for (const id of document.links || []) degree.set(id, (degree.get(id) || 0) + 1);
  const nodes = documents.map((document) => {
    const group = sectionIndex.get(document.section) || 0;
    const item = groupedIndex.get(document.section) || 0;
    groupedIndex.set(document.section, item + 1);
    const orbit = (group / Math.max(sections.length, 1)) * Math.PI * 2 - Math.PI / 2;
    const spiral = item * GOLDEN_ANGLE + fraction(document.id) * 1.7;
    const radius = 25 + Math.sqrt(item) * 43;
    return {
      id: document.id,
      title: document.title,
      section: document.section,
      path: document.path,
      x: Math.cos(orbit) * 155 + Math.cos(spiral) * radius,
      y: Math.sin(orbit) * 112 + Math.sin(spiral) * radius * .7,
      z: Math.sin(orbit * 1.7) * 115 + (fraction(document.id + ':z') - .5) * 125,
      weight: Math.min(18, 6 + Math.sqrt(degree.get(document.id) || 0) * 2.5),
      degree: degree.get(document.id) || 0,
    };
  });
  const known = new Set(nodes.map((node) => node.id));
  const seen = new Set();
  const edges = [];
  for (const document of documents) {
    for (const target of document.links || []) {
      if (!known.has(target) || target === document.id) continue;
      const key = [document.id, target].sort().join('|');
      if (seen.has(key)) continue;
      seen.add(key);
      edges.push({ source: document.id, target });
    }
  }
  return { nodes, edges, sections };
}

export function visibleGraph(graph, section = null) {
  if (!section) return graph;
  const nodes = graph.nodes.filter((node) => node.section === section);
  const ids = new Set(nodes.map((node) => node.id));
  return {
    nodes,
    edges: graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)),
    sections: graph.sections,
  };
}

export function projectGraph(nodes, { width, height, yaw = 0, pitch = 0, zoom = 1 }) {
  const sy = Math.sin(yaw);
  const cy = Math.cos(yaw);
  const sx = Math.sin(pitch);
  const cx = Math.cos(pitch);
  const fit = Math.min(1.15, Math.max(.42, width / 900));
  const originX = width < 700 ? width * .5 : width * .55;
  const originY = height * .52;
  return nodes.map((node) => {
    const turnedX = node.x * cy - node.z * sy;
    const turnedZ = node.x * sy + node.z * cy;
    const turnedY = node.y * cx - turnedZ * sx;
    const depth = node.y * sx + turnedZ * cx;
    const perspective = 730 / Math.max(290, 730 - depth);
    const scale = fit * zoom * perspective;
    return { ...node, x: originX + turnedX * scale, y: originY + turnedY * scale,
      depth, scale, radius: Math.max(4, node.weight * scale) };
  });
}

export function statusLabel(status) {
  if (status === 'active') return 'active';
  if (status === 'invalid') return 'invalid';
  return 'inactive';
}

export function flattenTree(tree, parentPath = '') {
  const out = [];
  if (!Array.isArray(tree)) return out;
  for (const node of tree) {
    if (!node || typeof node !== 'object') continue;
    const path = parentPath ? `${parentPath}/${node.name}` : node.name;
    if (node.kind === 'dir') {
      if (node.locked) {
        out.push({ path: `${path}/`, name: node.name, kind: 'locked-dir', locked: true, count: node.count ?? 0, mode: node.mode });
      } else if (Array.isArray(node.children)) {
        out.push(...flattenTree(node.children, path));
      } else {
        out.push({ path: `${path}/`, name: node.name, kind: 'dir' });
      }
    } else {
      out.push({ path, name: node.name, kind: 'file', size: Number(node.size) || 0 });
    }
  }
  return out;
}

export function fileSize(n) {
  const b = Number(n) || 0;
  if (b < 1024) return `${b}b`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)}kb`;
  return `${(b / (1024 * 1024)).toFixed(1)}mb`;
}

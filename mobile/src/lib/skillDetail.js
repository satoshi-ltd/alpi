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
        out.push({ path: `${path}/`, kind: 'locked-dir', count: node.count ?? 0, mode: node.mode });
      } else if (Array.isArray(node.children)) {
        out.push(...flattenTree(node.children, path));
      } else {
        out.push({ path: `${path}/`, kind: 'dir' });
      }
    } else {
      out.push({ path, kind: 'file' });
    }
  }
  return out;
}

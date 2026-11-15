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

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function skillVersion(detail) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(detail?.created_at ?? '').trim());
  const date = m && Number(m[2]) >= 1 && Number(m[2]) <= 12 ? `${MONTHS[Number(m[2]) - 1]} ${Number(m[3])}` : null;
  return [detail?.version ? `v${detail.version}` : null, detail?.origin || 'agent', date].filter(Boolean).join(' · ');
}

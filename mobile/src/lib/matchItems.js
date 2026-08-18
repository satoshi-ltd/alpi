export function matchItems(items, query) {
  const needle = String(query ?? '').replace(/^[@#]/, '').trim().toLowerCase();
  if (!needle) return items;
  return items.filter((it) => {
    const id = (it.id ?? '').toLowerCase();
    const name = (it.name ?? '').toLowerCase();
    return id.includes(needle) || name.includes(needle);
  });
}

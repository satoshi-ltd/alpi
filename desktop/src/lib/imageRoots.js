// Active profile's workspace root(s) — model controls only the path, never these.
let roots = [];

export function setImageRoots(next) {
  roots = (next || []).filter(Boolean);
}

export function getImageRoots() {
  return roots;
}

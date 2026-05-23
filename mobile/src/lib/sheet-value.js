export function nextSheetValue({ current, newInitial, prevInitial }) {
  if (prevInitial === null) return newInitial;
  return current === prevInitial ? newInitial : current;
}

export function navigateMenu(event, root) {
  const key = event.key;
  if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(key)) return;
  const editing = event.target.matches("input, textarea");
  if (editing && (key === "Home" || key === "End")) return;
  const items = [...root.querySelectorAll("button:not(:disabled)")];
  if (!items.length) return;
  event.preventDefault();
  event.stopPropagation();
  const index = items.indexOf(document.activeElement);
  const next = key === "Home" ? 0 : key === "End" ? items.length - 1
    : key === "ArrowDown" ? (index + 1) % items.length
      : (index < 0 ? items.length - 1 : (index - 1 + items.length) % items.length);
  items[next].focus();
}

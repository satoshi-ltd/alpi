export const GAZE_TAU_MS = 60;
export const GAZE_REACH_PX = 260;
export const GAZE_REST_MS = 2600;
export const TYPING_LOOK = { x: 0, y: 1 };
const SETTLED = 0.002;

const marks = new Map();
let pointer = null;
let typing = false;
let resting = false;
let dirty = false;
let frame = 0;
let last = 0;
let restTimer = 0;

const isField = (el) => !!el && (el.tagName === "TEXTAREA" || el.isContentEditable || (el.tagName === "INPUT" && el.type === "text"));

function targetFor(entry) {
  if (typing && entry.look) return TYPING_LOOK;
  if (!pointer || resting) return { x: 0, y: 0 };
  const box = entry.el.getBoundingClientRect();
  const dx = pointer.x - (box.left + box.width / 2);
  const dy = pointer.y - (box.top + box.height / 2);
  const reach = Math.hypot(dx, dy) || 1;
  const pull = Math.min(1, reach / GAZE_REACH_PX);
  return { x: (dx / reach) * pull, y: (dy / reach) * pull };
}

function write(entry) {
  entry.el.style.setProperty("--gx", entry.x.toFixed(3));
  entry.el.style.setProperty("--gy", entry.y.toFixed(3));
}

function tick(now) {
  frame = 0;
  const dt = last ? Math.min(now - last, 64) : 16;
  last = now;
  if (dirty) {
    dirty = false;
    for (const entry of marks.values()) entry.target = targetFor(entry);
  }
  const alpha = 1 - Math.exp(-dt / GAZE_TAU_MS);
  let moving = false;
  for (const entry of marks.values()) {
    const ex = entry.target.x - entry.x;
    const ey = entry.target.y - entry.y;
    if (Math.abs(ex) < SETTLED && Math.abs(ey) < SETTLED) {
      if (entry.x !== entry.target.x || entry.y !== entry.target.y) {
        entry.x = entry.target.x;
        entry.y = entry.target.y;
        write(entry);
      }
      continue;
    }
    entry.x += ex * alpha;
    entry.y += ey * alpha;
    write(entry);
    moving = true;
  }
  if (moving || dirty) schedule();
  else last = 0;
}

function schedule() {
  if (!frame) frame = requestAnimationFrame(tick);
}

function mark() {
  dirty = true;
  schedule();
}

function retarget() {
  typing = isField(document.activeElement);
  mark();
}

function onMove(event) {
  pointer = { x: event.clientX, y: event.clientY };
  resting = false;
  clearTimeout(restTimer);
  restTimer = setTimeout(() => {
    resting = true;
    retarget();
  }, GAZE_REST_MS);
  retarget();
}

function onFocusIn(event) {
  if (!isField(event.target)) return;
  typing = true;
  mark();
}

function onFocusOut(event) {
  if (!isField(event.target)) return;
  typing = false;
  mark();
}

function onBlur() {
  pointer = null;
  retarget();
}

function listen(on) {
  const method = on ? "addEventListener" : "removeEventListener";
  window[method]("mousemove", onMove, { passive: true });
  window[method]("blur", onBlur);
  document[method]("focusin", onFocusIn);
  document[method]("focusout", onFocusOut);
}

export function followPointer(el, { look = false } = {}) {
  if (!el || typeof window === "undefined") return () => {};
  if (!marks.size) listen(true);
  const entry = { el, look, x: 0, y: 0, target: { x: 0, y: 0 } };
  marks.set(el, entry);
  retarget();
  return () => {
    marks.delete(el);
    el.style.removeProperty("--gx");
    el.style.removeProperty("--gy");
    if (marks.size) return;
    listen(false);
    cancelAnimationFrame(frame);
    clearTimeout(restTimer);
    frame = 0;
    last = 0;
    pointer = null;
    typing = false;
    resting = false;
    dirty = false;
  };
}

export function trackedCount() {
  return marks.size;
}

const FAMILIES = [
  ['brain', /^memory$|memory/],
  ['file', /^(read_file|write_file|edit_file|delete_file|list_dir|attach_file|read_image|workspace|workgroup_file)$|_file$|^edit$|^ls$|^glob$/],
  ['terminal', /^(terminal|shell|run|bash|exec)$|terminal|shell/],
  ['globe', /^(web_fetch|web_search|web_extract|browser|research)$|^web_|browser/],
  ['search', /^(grep|search|find)$|search|grep|^find/],
  ['link', /^(peer|alp|send_message|notify|email|delegate|workgroup_post)$|^peer|^alp/],
];

export function toolFamily(name) {
  const n = String(name ?? '').toLowerCase();
  for (const [icon, re] of FAMILIES) if (re.test(n)) return icon;
  return 'cpu';
}

function parseArgs(args) {
  if (typeof args !== 'string') return args ?? null;
  const t = args.trim();
  if (!t.startsWith('{') && !t.startsWith('[')) return args;
  try {
    return JSON.parse(t);
  } catch {
    return args;
  }
}

const COMMAND_KEYS = ['command', 'cmd', 'script'];
const SUMMARY_KEYS = ['command', 'cmd', 'path', 'file', 'url', 'query', 'q', 'pattern', 'name', 'peer_id', 'channel', 'text', 'question'];

function oneLine(s, max = 80) {
  const flat = String(s).replace(/\s+/g, ' ').trim();
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat;
}

export function toolCommand(args) {
  const a = parseArgs(args);
  if (typeof a === 'string') return a.trim() || null;
  if (!a || typeof a !== 'object') return null;
  for (const k of COMMAND_KEYS) if (typeof a[k] === 'string' && a[k].trim()) return a[k];
  return null;
}

export function toolSummary(args) {
  const a = parseArgs(args);
  if (a == null) return '';
  if (typeof a !== 'object') return oneLine(a);
  if (Array.isArray(a)) return oneLine(a.join(' '));
  for (const k of SUMMARY_KEYS) {
    const v = a[k];
    if (typeof v === 'string' && v.trim()) return oneLine(v);
  }
  const first = Object.values(a).find((v) => typeof v === 'string' || typeof v === 'number');
  return first != null ? oneLine(first) : '';
}

export function prettyArgs(args) {
  const a = parseArgs(args);
  if (a == null) return '';
  if (typeof a === 'string') return a;
  try {
    return JSON.stringify(a, null, 2);
  } catch {
    return String(a);
  }
}

export function toolOutput(tool) {
  const live = typeof tool?.output === 'string' && tool.output ? tool.output : null;
  const text = live ?? (typeof tool?.result === 'string' ? tool.result : '');
  const excerpt = text.endsWith('…') && text.length >= 399;
  return { text, excerpt };
}

export function fmtToolDuration(seconds) {
  const s = Number(seconds);
  if (!Number.isFinite(s) || s <= 0) return '';
  if (s < 10) return `${s.toFixed(1)}s`;
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return r ? `${m}m ${r}s` : `${m}m`;
}

export function toolTitle(tool, status) {
  const name = tool?.name ?? 'tool';
  const dur = fmtToolDuration(tool?.duration_s);
  if (status === 'running') return `${name} · running`;
  if (status === 'error') return dur ? `${name} · failed in ${dur}` : `${name} · failed`;
  return dur ? `${name} · ${dur}` : name;
}

export function failureLine(tool) {
  const { text } = toolOutput(tool);
  const line = text.split('\n').map((l) => l.trim()).find(Boolean);
  return line ? oneLine(line, 120) : 'failed';
}

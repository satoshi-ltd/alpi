import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = join(import.meta.dirname, '..', '..');

const walk = (dir) =>
  readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return walk(path);
    return /\.jsx?$/.test(entry.name) && !/\.test\.jsx?$/.test(entry.name) ? [path] : [];
  });

const spokenOnly = (source) => source
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/(^|[^:'"`])\/\/.*$/gm, '$1')
  .replace(/accessibilityLabel=(\{[^}\n]*\}|"[^"\n]*"|'[^'\n]*')/g, '')
  .replace(/<(ListSkeleton|ReaderSkeleton|InboxSkeleton)\b[^>]*>/g, '');

const PROGRESS = /\b(loading|syncing|fetching)\b/i;
const VISIBLE_PROP = /\b(title|subtitle|meta|label|helper|value|placeholder|hint|text|message)=("[^"\n]*"|'[^'\n]*'|\{[^\n]*)/g;
const LITERAL = /["'`]([^"'`\n]*)["'`]/g;

const bareLoading = (source) => {
  const spoken = spokenOnly(source);
  const jsxText = [...spoken.matchAll(/>([^<>{}'"`=;()]*)</g)].some((m) => PROGRESS.test(m[1]));
  const prop = [...spoken.matchAll(VISIBLE_PROP)].some((m) => [...m[2].matchAll(LITERAL)].some((l) => PROGRESS.test(l[1])) || (m[2].startsWith('"') && PROGRESS.test(m[2])));
  const literal = [...spoken.matchAll(LITERAL)].some((l) => /\b(loading|syncing|fetching)(…|\.\.\.)/i.test(l[1]) || /\b(Loading|Syncing|Fetching|LOADING|SYNCING|FETCHING)\b/.test(l[1]));
  return jsxText || prop || literal || /\bLoading\b|\bLOADING\b/.test(spoken);
};

describe('every wait is alpi’s own', () => {
  const files = [...walk(join(ROOT, 'src')), ...walk(join(ROOT, 'app'))];

  it('imports no platform ActivityIndicator anywhere in a screen or component', () => {
    const found = files.filter((path) => /\bActivityIndicator\b/.test(readFileSync(path, 'utf8'))).map((path) => relative(ROOT, path));
    expect(found).toEqual([]);
  });

  it.each([
    ['a row label', '<Row label="Loading usage…" chevron={false} />'],
    ['a conditional row label', "label={busy ? 'Loading storage…' : EMPTY.storage.title}"],
    ['multi-line JSX text', '<Text\n  style={x}\n>\n  Loading the file\n</Text>'],
    ['a visible Busy label', '<Busy label="Loading skills" />'],
    ['a ScreenHeader subtitle', 'subtitle="PROFILE · LOADING"'],
    ['a lowercase meta', 'meta="loading"'],
    ['lowercase JSX text', '<Text>loading</Text>'],
    ['lowercase multi-line JSX text', '<Text style={s}>\n  loading\n</Text>'],
    ['a syncing word', '<Text>Syncing…</Text>'],
    ['a fetching word', "<Row label={busy ? 'Fetching…' : 'Done'} />"],
    ['a fetching label', '<Busy label="Fetching earlier messages" />'],
    ['a lowercase helper', 'helper="syncing with the daemon"'],
    ['a ChatHeader meta', 'meta="loading…"'],
    ['a conditional subtitle', "subtitle={busy ? 'LOADING' : 'NOT FOUND'}"],
    ['a bare word', '<Text>Loading…</Text>'],
  ])('catches %s', (_, source) => {
    expect(bareLoading(source)).toBe(true);
  });

  it('leaves state names and accessibility labels alone', () => {
    expect(bareLoading("notify({ kind: 'loading', voiceId });")).toBe(false);
    expect(bareLoading('<ListSkeleton label="Loading skills" />')).toBe(false);
    expect(bareLoading('<ReaderSkeleton\n  label="Loading the file"\n/>')).toBe(false);
    expect(bareLoading('<View accessible accessibilityLabel="Loading usage" />')).toBe(false);
    expect(bareLoading("<InboxSkeleton rows={4} label={`Loading ${x}`} />")).toBe(false);
    expect(bareLoading('const [isLoading, setLoading] = useState(true);')).toBe(false);
    expect(bareLoading("setState(s?.kind === 'playing' || s?.kind === 'loading' ? s : null)")).toBe(false);
    expect(bareLoading('<SyncBar syncing={summary.loading} />')).toBe(false);
    expect(bareLoading('<Button title="Save" loading={busy} />')).toBe(false);
    expect(bareLoading('const settingsSyncing = snap.loading || storage.loading;')).toBe(false);
    expect(bareLoading('<View accessibilityLabel="Fetching the run" />')).toBe(false);
    expect(bareLoading('<ListSkeleton label="Syncing schedules" />')).toBe(false);
  });

  it('never says Loading in a header subtitle, a meta line or a bare word', () => {
    const found = files.filter((path) => bareLoading(readFileSync(path, 'utf8'))).map((path) => relative(ROOT, path));
    expect(found).toEqual([]);
  });
});

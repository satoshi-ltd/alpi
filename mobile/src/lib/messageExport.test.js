import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  written: [],
  shared: [],
  printed: [],
  moved: [],
  deleted: [],
  dirs: [],
  available: true,
}));

vi.mock('expo-file-system/legacy', () => ({
  cacheDirectory: 'file:///cache/',
  writeAsStringAsync: vi.fn(async (uri, content) => { h.written.push({ uri, content }); }),
  makeDirectoryAsync: vi.fn(async (uri, opts) => { h.dirs.push({ uri, opts }); }),
  deleteAsync: vi.fn(async (uri, opts) => { h.deleted.push({ uri, opts }); }),
  moveAsync: vi.fn(async (args) => { h.moved.push(args); }),
}));
vi.mock('expo-print', () => ({
  printToFileAsync: vi.fn(async (opts) => { h.printed.push(opts); return { uri: 'file:///tmp/Print-1.pdf' }; }),
}));
vi.mock('expo-sharing', () => ({
  isAvailableAsync: vi.fn(async () => h.available),
  shareAsync: vi.fn(async (uri, opts) => { h.shared.push({ uri, opts }); }),
}));

import { shareMarkdown, sharePdf, wgPostSeconds } from './messageExport';

const CHART = '```chart\n{"type": "bar", "title": "Chats", "x": ["Mon", "Tue"], "series": [{"name": "Chats", "values": [3, 5]}]}\n```';
const MESSAGE = { title: 'Weekly chat report', profile: 'pulse', server: 'casa', at: 1792944000, body: `Chats went up.\n\n${CHART}` };

beforeEach(() => {
  for (const key of ['written', 'shared', 'printed', 'moved', 'deleted', 'dirs']) h[key].length = 0;
  h.available = true;
});

describe('mobile message export', () => {
  it('writes the markdown into the cache and shares it', async () => {
    await shareMarkdown(MESSAGE);
    expect(h.written).toHaveLength(1);
    expect(h.written[0].uri).toMatch(/^file:\/\/\/cache\/alpi-export-[a-z0-9]+-\d+\/weekly-chat-report\.md$/);
    expect(h.written[0].content).toContain('# Weekly chat report');
    expect(h.written[0].content).toContain('_@pulse · casa · ');
    expect(h.written[0].content).toContain('```chart');
    expect(h.shared[0]).toEqual({
      uri: h.written[0].uri,
      opts: { mimeType: 'text/markdown', UTI: 'net.daringfireball.markdown', dialogTitle: 'weekly-chat-report.md' },
    });
  });

  it('prints the message to an A4 PDF with its chart and footer, names it and shares it', async () => {
    await sharePdf(MESSAGE, '#3fb37a');
    expect(h.printed).toHaveLength(1);
    expect(h.printed[0]).toMatchObject({ width: 595, height: 842 });
    expect(h.printed[0].html).toContain('<svg');
    expect(h.printed[0].html).toContain('Chats went up.');
    expect(h.printed[0].html).toContain('@pulse on casa');
    expect(h.printed[0].html).toContain('--chart-1: #3fb37a');
    expect(h.moved).toHaveLength(1);
    expect(h.moved[0].from).toBe('file:///tmp/Print-1.pdf');
    expect(h.moved[0].to).toMatch(/^file:\/\/\/cache\/alpi-export-[a-z0-9]+-\d+\/weekly-chat-report\.pdf$/);
    expect(h.shared[0].uri).toBe(h.moved[0].to);
    expect(h.shared[0].opts).toEqual({ mimeType: 'application/pdf', UTI: 'com.adobe.pdf', dialogTitle: 'weekly-chat-report.pdf' });
  });

  it('gives every export its own folder, so a same-name export never replaces a file still being shared', async () => {
    await shareMarkdown(MESSAGE);
    await shareMarkdown(MESSAGE);
    await sharePdf(MESSAGE);
    await sharePdf(MESSAGE);
    const folders = h.dirs.map((d) => d.uri);
    expect(new Set(folders).size).toBe(4);
    expect(h.dirs.every((d) => d.opts.intermediates === true)).toBe(true);
    const files = [...h.written.map((w) => w.uri), ...h.moved.map((m) => m.to)];
    expect(new Set(files).size).toBe(4);
    expect(files.every((f) => f.endsWith('/weekly-chat-report.md') || f.endsWith('/weekly-chat-report.pdf'))).toBe(true);
    expect(h.deleted).toEqual([]);
  });

  it('keeps a fresh export for a slow share target and clears its folder once it is old', async () => {
    vi.useFakeTimers();
    try {
      await shareMarkdown(MESSAGE);
      const first = h.dirs[0].uri;
      await sharePdf({ ...MESSAGE, title: 'Second' });
      expect(h.deleted.map((d) => d.uri)).not.toContain(first);
      vi.advanceTimersByTime(10 * 60 * 1000 + 1);
      h.deleted.length = 0;
      await shareMarkdown({ ...MESSAGE, title: 'Third' });
      expect(h.deleted.map((d) => d.uri)).toEqual(expect.arrayContaining([first, h.dirs[1].uri]));
      expect(h.deleted.map((d) => d.uri)).not.toContain(h.dirs[2].uri);
    } finally {
      vi.useRealTimers();
    }
  });

  it('refuses when sharing is unavailable instead of failing silently', async () => {
    h.available = false;
    await expect(shareMarkdown(MESSAGE)).rejects.toThrow('sharing is not available');
    await expect(sharePdf(MESSAGE)).rejects.toThrow('sharing is not available');
    expect(h.shared).toHaveLength(0);
  });

  it('reads a workgroup post time from its ISO string', () => {
    expect(wgPostSeconds('2026-10-07T10:00:00Z')).toBe(Date.parse('2026-10-07T10:00:00Z') / 1000);
    expect(wgPostSeconds('')).toBe(0);
    expect(wgPostSeconds('not a date')).toBe(0);
    expect(wgPostSeconds(undefined)).toBe(0);
  });
});

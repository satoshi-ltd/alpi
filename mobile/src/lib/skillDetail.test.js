import { describe, expect, it } from 'vitest';

import { fileSize, flattenTree, statusLabel } from './skillDetail';

describe('statusLabel', () => {
  it.each([
    ['active', 'active'],
    ['invalid', 'invalid'],
    ['inactive', 'inactive'],
    ['', 'inactive'],
    [undefined, 'inactive'],
  ])('maps %s → %s', (input, want) => expect(statusLabel(input)).toBe(want));
});

describe('flattenTree', () => {
  it('returns [] for non-array input', () => {
    expect(flattenTree(null)).toEqual([]);
    expect(flattenTree(undefined)).toEqual([]);
  });

  it('walks nested dirs and yields prefixed paths for each file', () => {
    const tree = [
      { name: 'README.md', kind: 'file' },
      {
        name: 'scripts',
        kind: 'dir',
        children: [
          { name: 'run.py', kind: 'file' },
          { name: 'helpers', kind: 'dir', children: [{ name: 'fmt.py', kind: 'file' }] },
        ],
      },
    ];
    expect(flattenTree(tree).map((n) => n.path)).toEqual([
      'README.md',
      'scripts/run.py',
      'scripts/helpers/fmt.py',
    ]);
  });

  it('represents a locked secrets/ dir as a single locked-dir node (never lists its files)', () => {
    const tree = [
      { name: 'secrets', kind: 'dir', locked: true, count: 3, mode: '0700' },
      { name: 'plain.txt', kind: 'file' },
    ];
    const flat = flattenTree(tree);
    expect(flat).toEqual([
      { path: 'secrets/', name: 'secrets', kind: 'locked-dir', locked: true, count: 3, mode: '0700' },
      { path: 'plain.txt', name: 'plain.txt', kind: 'file', size: 0 },
    ]);
  });

  it('carries each file name and size so the page can type and size it', () => {
    const flat = flattenTree([{ name: 'state', kind: 'dir', children: [{ name: 'db.sqlite', kind: 'file', size: 49152 }] }]);
    expect(flat).toEqual([{ path: 'state/db.sqlite', name: 'db.sqlite', kind: 'file', size: 49152 }]);
    expect(fileSize(49152)).toBe('48.0kb');
  });
});

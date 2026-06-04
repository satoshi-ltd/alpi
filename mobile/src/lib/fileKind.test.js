import { describe, expect, it } from 'vitest';

import { fileKind, fileTypeLabel, fmtSize } from './fileKind';

describe('fileKind', () => {
  it('classifies images by mime', () => {
    expect(fileKind('shot.png', 'image/png')).toBe('image');
    expect(fileKind('x.jpeg', 'image/jpeg')).toBe('image');
  });

  it('classifies code by extension', () => {
    expect(fileKind('main.py', 'text/plain')).toBe('code');
    expect(fileKind('app.tsx', '')).toBe('code');
    expect(fileKind('data.json', 'application/json')).toBe('code');
  });

  it('classifies prose text by extension', () => {
    expect(fileKind('notes.md', 'text/markdown')).toBe('text');
    expect(fileKind('a.csv', 'text/csv')).toBe('text');
  });

  it('treats pdf and unknown as generic file', () => {
    expect(fileKind('doc.pdf', 'application/pdf')).toBe('file');
    expect(fileKind('mystery', '')).toBe('file');
  });
});

describe('fileTypeLabel', () => {
  it('uses the mime subtype, falling back to extension', () => {
    expect(fileTypeLabel('doc.pdf', 'application/pdf')).toBe('pdf');
    expect(fileTypeLabel('a.png', 'image/png')).toBe('png');
    expect(fileTypeLabel('notes.md', '')).toBe('md');
  });
});

describe('fmtSize', () => {
  it('formats bytes, KB and MB', () => {
    expect(fmtSize(500)).toBe('500 B');
    expect(fmtSize(2048)).toBe('2 KB');
    expect(fmtSize(3 * 1024 * 1024)).toBe('3.0 MB');
    expect(fmtSize(undefined)).toBe('0 B');
  });
});

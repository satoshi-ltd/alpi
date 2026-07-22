import { describe, expect, it, vi } from 'vitest';
import {
  FETCH_TIMEOUT_MS, MAX_FILE_BYTES, MAX_TEXT_FILE_BYTES,
  attachmentByteCap, imageCacheKey, mimeFor, oversizeError,
  resolveAttachmentMime, stageAttachment,
} from './attachments';

describe('imageCacheKey', () => {
  it('namespaces by endpoint so two daemons with the same profile/path do not collide', () => {
    expect(imageCacheKey('c-A', 'default', '/tmp/x.png'))
      .not.toBe(imageCacheKey('c-B', 'default', '/tmp/x.png'));
  });

  it('is stable for the same endpoint/profile/path', () => {
    expect(imageCacheKey('c-A', 'default', '/tmp/x.png')).toBe('c-A:default:/tmp/x.png');
  });

  it('tolerates a missing endpoint id', () => {
    expect(imageCacheKey(undefined, 'default', '/p')).toBe(':default:/p');
  });
});

describe('mimeFor', () => {
  it('maps known extensions', () => {
    expect(mimeFor('shot.PNG')).toBe('image/png');
    expect(mimeFor('a.jpeg')).toBe('image/jpeg');
    expect(mimeFor('doc.pdf')).toBe('application/pdf');
    expect(mimeFor('notes.md')).toBe('text/markdown');
    expect(mimeFor('data.csv')).toBe('text/csv');
    expect(mimeFor('cfg.yaml')).toBe('application/yaml');
  });
  it('maps the supported code extensions to text/plain', () => {
    expect(mimeFor('main.py')).toBe('text/plain');
    expect(mimeFor('app.tsx')).toBe('text/plain');
    expect(mimeFor('q.sql')).toBe('text/plain');
  });
  it('returns the fallback for unknown (zip, and code outside the set)', () => {
    expect(mimeFor('x.zip', '')).toBe('');
    expect(mimeFor('a.rb', '')).toBe('');
  });
});

describe('stageAttachment', () => {
  it('calls host.attachments.stage with the useEndpoint (method, params) signature and returns metadata', async () => {
    const call = vi.fn().mockResolvedValue({
      ok: true,
      attachment: { path: '/d/tmp/x/scan.pdf', name: 'scan.pdf', mime: 'application/pdf', size: 9 },
    });
    const out = await stageAttachment(call, {
      profile: 'default', name: 'scan.pdf', mime: 'application/pdf', base64: 'AAAA',
    });
    expect(call).toHaveBeenCalledWith('host.attachments.stage', {
      profile: 'default', name: 'scan.pdf', mime: 'application/pdf', data_base64: 'AAAA',
    }, { timeoutMs: FETCH_TIMEOUT_MS });
    expect(out.path).toBe('/d/tmp/x/scan.pdf');
  });

  it('uploads with the 60s attachments timeout, not the default RPC window', async () => {
    const call = vi.fn().mockResolvedValue({ ok: true, attachment: { path: '/p', name: 'a.png', mime: 'image/png', size: 1 } });
    await stageAttachment(call, { profile: 'default', name: 'a.png', mime: 'image/png', base64: 'AA' });
    expect(call.mock.calls[0][2]).toEqual({ timeoutMs: 60_000 });
  });

  it('rejects an over-cap file before building the upload call', async () => {
    const call = vi.fn();
    await expect(
      stageAttachment(call, {
        profile: 'default', name: 'huge.pdf', mime: 'application/pdf',
        base64: 'AA', size: MAX_FILE_BYTES + 1,
      }),
    ).rejects.toThrow(/too large \(20 MB max\)/);
    expect(call).not.toHaveBeenCalled();
  });

  it('applies the tighter 2 MiB cap to text mimes', async () => {
    const call = vi.fn();
    await expect(
      stageAttachment(call, {
        profile: 'default', name: 'big.txt', mime: 'text/plain',
        base64: 'AA', size: MAX_TEXT_FILE_BYTES + 1,
      }),
    ).rejects.toThrow(/too large \(2 MB max\)/);
    expect(call).not.toHaveBeenCalled();
  });

  it('falls back to the base64 length when the picker reports no size', async () => {
    const call = vi.fn();
    const oversized = Buffer.alloc(MAX_TEXT_FILE_BYTES + 1).toString('base64');
    await expect(
      stageAttachment(call, {
        profile: 'default', name: 'big.txt', mime: 'text/plain', base64: oversized,
      }),
    ).rejects.toThrow(/too large/);
    expect(call).not.toHaveBeenCalled();
  });

  it('base64 fallback accepts a file exactly at the cap (padding not counted)', async () => {
    const call = vi.fn().mockResolvedValue({ ok: true, attachment: { path: '/p', name: 'b.txt', mime: 'text/plain', size: MAX_TEXT_FILE_BYTES } });
    const atCap = Buffer.alloc(MAX_TEXT_FILE_BYTES).toString('base64');
    await stageAttachment(call, {
      profile: 'default', name: 'b.txt', mime: 'text/plain', base64: atCap,
    });
    expect(call).toHaveBeenCalled();
  });

  it('allows a file exactly at the cap', async () => {
    const call = vi.fn().mockResolvedValue({ ok: true, attachment: { path: '/p', name: 'a.pdf', mime: 'application/pdf', size: MAX_FILE_BYTES } });
    await stageAttachment(call, {
      profile: 'default', name: 'a.pdf', mime: 'application/pdf', base64: 'AA', size: MAX_FILE_BYTES,
    });
    expect(call).toHaveBeenCalled();
  });

  it('caps by resolved mime: text caps apply even when the picker omits the mime', () => {
    expect(attachmentByteCap('text/plain')).toBe(MAX_TEXT_FILE_BYTES);
    expect(attachmentByteCap('application/pdf')).toBe(MAX_FILE_BYTES);
    expect(attachmentByteCap('application/octet-stream')).toBe(MAX_FILE_BYTES);
  });
});

describe('picker preflight helpers', () => {
  it('oversizeError fires above the cap and stays silent at it', () => {
    expect(oversizeError('a.pdf', 'application/pdf', MAX_FILE_BYTES)).toBeNull();
    expect(oversizeError('a.pdf', 'application/pdf', MAX_FILE_BYTES + 1)).toMatch(/20 MB max/);
    expect(oversizeError('a.txt', 'text/plain', MAX_TEXT_FILE_BYTES + 1)).toMatch(/2 MB max/);
  });

  it('resolveAttachmentMime prefers a known picker mime and falls back by extension', () => {
    expect(resolveAttachmentMime('a.png', 'image/png')).toBe('image/png');
    expect(resolveAttachmentMime('notes.md', undefined)).toBe('text/markdown');
    expect(resolveAttachmentMime('run.fit', 'application/x-whatever')).toBe('application/octet-stream');
  });

  it('infers mime from the name when missing', async () => {
    const call = vi.fn().mockResolvedValue({ ok: true, attachment: { path: '/p', name: 'a.png', mime: 'image/png', size: 1 } });
    await stageAttachment(call, { profile: 'default', name: 'a.png', base64: 'AA' });
    expect(call.mock.calls[0][1].mime).toBe('image/png');
  });

  it('stages an unknown type as an opaque octet-stream file', async () => {
    const call = vi.fn().mockResolvedValue({ ok: true, attachment: { path: '/p', name: 'run.fit', mime: 'application/octet-stream', size: 1 } });
    await stageAttachment(call, { profile: 'default', name: 'run.fit', base64: 'AA' });
    expect(call.mock.calls[0][1].mime).toBe('application/octet-stream');
  });

  it('raises a clear error when the daemon rejects', async () => {
    const call = vi.fn().mockRejectedValue(new Error('too large'));
    await expect(
      stageAttachment(call, { profile: 'default', name: 'a.png', mime: 'image/png', base64: 'AA' }),
    ).rejects.toThrow(/could not upload a.png/);
  });
});

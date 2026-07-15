import { describe, expect, it, vi } from 'vitest';
import { imageCacheKey, mimeFor, stageAttachment } from './attachments';

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
    });
    expect(out.path).toBe('/d/tmp/x/scan.pdf');
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

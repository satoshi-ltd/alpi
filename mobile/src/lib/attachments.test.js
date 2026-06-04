import { describe, expect, it, vi } from 'vitest';
import { mimeFor, stageAttachment } from './attachments';

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
  const ENDPOINT = { id: 'conn-a' };

  it('calls host.attachments.stage with the right payload and returns metadata', async () => {
    const call = vi.fn().mockResolvedValue({
      ok: true,
      attachment: { path: '/d/tmp/x/scan.pdf', name: 'scan.pdf', mime: 'application/pdf', size: 9 },
    });
    const out = await stageAttachment(call, ENDPOINT, {
      profile: 'default', name: 'scan.pdf', mime: 'application/pdf', base64: 'AAAA',
    });
    expect(call).toHaveBeenCalledWith(ENDPOINT, 'host.attachments.stage', {
      profile: 'default', name: 'scan.pdf', mime: 'application/pdf', data_base64: 'AAAA',
    });
    expect(out.path).toBe('/d/tmp/x/scan.pdf');
  });

  it('infers mime from the name when missing', async () => {
    const call = vi.fn().mockResolvedValue({ ok: true, attachment: { path: '/p', name: 'a.png', mime: 'image/png', size: 1 } });
    await stageAttachment(call, ENDPOINT, { profile: 'default', name: 'a.png', base64: 'AA' });
    expect(call.mock.calls[0][2].mime).toBe('image/png');
  });

  it('rejects an unsupported type before calling', async () => {
    const call = vi.fn();
    await expect(
      stageAttachment(call, ENDPOINT, { profile: 'default', name: 'a.zip', base64: 'AA' }),
    ).rejects.toThrow(/unsupported/);
    expect(call).not.toHaveBeenCalled();
  });

  it('raises a clear error when the daemon rejects', async () => {
    const call = vi.fn().mockRejectedValue(new Error('too large'));
    await expect(
      stageAttachment(call, ENDPOINT, { profile: 'default', name: 'a.png', mime: 'image/png', base64: 'AA' }),
    ).rejects.toThrow(/could not upload a.png/);
  });
});

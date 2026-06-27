import { describe, expect, it } from 'vitest';

import {
  IMAP_FIELDS,
  buildAddPayload,
  emailSlug,
  isAddReady,
  isValidEmail,
  portValid,
} from './emailAccounts';

describe('emailSlug', () => {
  it.each([
    ['you@domain.com', 'you_domain_com'],
    ['Jane.Doe@Example.CO.UK', 'jane_doe_example_co_uk'],
    ['  spaced+tag@x.io  ', 'spaced_tag_x_io'],
  ])('slugs %s -> %s', (input, expected) => {
    expect(emailSlug(input)).toBe(expected);
  });

  it('returns empty for nullish', () => {
    expect(emailSlug(undefined)).toBe('');
    expect(emailSlug(null)).toBe('');
  });
});

describe('isValidEmail', () => {
  it.each(['a@b.co', 'you@domain.com', 'x.y+z@sub.example.org'])('accepts %s', (e) => {
    expect(isValidEmail(e)).toBe(true);
  });

  it.each(['', 'nope', 'a@b', 'a@b.', '@b.co', 'a b@c.co'])('rejects %s', (e) => {
    expect(isValidEmail(e)).toBe(false);
  });
});

describe('isAddReady', () => {
  const full = {
    address: 'you@domain.com',
    password: 'secret',
    imap_host: 'imap.domain.com',
    smtp_host: 'smtp.domain.com',
  };

  it('is ready when address, password and both hosts are present', () => {
    expect(isAddReady(full)).toBe(true);
  });

  it.each([
    ['bad address', { ...full, address: 'nope' }],
    ['no password', { ...full, password: '' }],
    ['no imap host', { ...full, imap_host: '' }],
    ['no smtp host', { ...full, smtp_host: '' }],
    ['non-numeric imap port', { ...full, imap_port: 'abc' }],
    ['out-of-range smtp port', { ...full, smtp_port: '70000' }],
  ])('is not ready: %s', (_label, draft) => {
    expect(isAddReady(draft)).toBe(false);
  });

  it('is not ready on empty draft', () => {
    expect(isAddReady({})).toBe(false);
  });
});

describe('buildAddPayload', () => {
  it('trims strings and omits blank ports', () => {
    const payload = buildAddPayload('work', {
      address: '  you@domain.com ',
      password: 'pw',
      imap_host: ' imap.domain.com ',
      smtp_host: ' smtp.domain.com ',
      imap_port: '',
      smtp_port: '',
    });
    expect(payload).toEqual({
      profile: 'work',
      address: 'you@domain.com',
      password: 'pw',
      imap_host: 'imap.domain.com',
      smtp_host: 'smtp.domain.com',
    });
  });

  it('coerces provided ports to numbers', () => {
    const payload = buildAddPayload('work', {
      address: 'you@domain.com',
      password: 'pw',
      imap_host: 'imap.domain.com',
      smtp_host: 'smtp.domain.com',
      imap_port: '993',
      smtp_port: '587',
    });
    expect(payload.imap_port).toBe(993);
    expect(payload.smtp_port).toBe(587);
  });

  it('omits invalid ports instead of sending NaN', () => {
    const payload = buildAddPayload('work', {
      address: 'you@domain.com',
      password: 'pw',
      imap_host: 'imap.domain.com',
      smtp_host: 'smtp.domain.com',
      imap_port: 'abc',
      smtp_port: '70000',
    });
    expect('imap_port' in payload).toBe(false);
    expect('smtp_port' in payload).toBe(false);
  });
});

describe('portValid', () => {
  it.each(['', '993', '1', '65535'])('accepts %s', (p) => {
    expect(portValid(p)).toBe(true);
  });

  it.each(['abc', '0', '70000', '-1', '99.5', '12x'])('rejects %s', (p) => {
    expect(portValid(p)).toBe(false);
  });
});

describe('IMAP_FIELDS', () => {
  it('covers the add-form schema in order', () => {
    expect(IMAP_FIELDS.map((f) => f.key)).toEqual([
      'address',
      'password',
      'imap_host',
      'imap_port',
      'smtp_host',
      'smtp_port',
    ]);
  });

  it('marks only the password field secret', () => {
    expect(IMAP_FIELDS.filter((f) => f.secret).map((f) => f.key)).toEqual(['password']);
  });
});

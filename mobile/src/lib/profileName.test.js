import { describe, expect, it } from 'vitest';

import {
  PROFILE_NAME_RE,
  RESERVED_PROFILE_NAMES,
  isValidProfileName,
  profileNameError,
} from './profileName';

describe('PROFILE_NAME_RE', () => {
  it.each(['work', 'personal', 'home-server', 'build.debug', 'a', '0', 'a1', 'a_b'])(
    'accepts %s',
    (name) => expect(PROFILE_NAME_RE.test(name)).toBe(true),
  );

  it.each([
    '',
    '.hidden',
    '-leading-dash',
    '_leading-underscore',
    'with space',
    'caps-Off',
    '../escape',
    'a/b',
    '..',
  ])('rejects %s', (name) => expect(PROFILE_NAME_RE.test(name)).toBe(false));
});

describe('isValidProfileName', () => {
  it.each(['work', 'build.debug', 'a.b.c', 'a', '0', 'x_y-z'])(
    'accepts %s',
    (name) => expect(isValidProfileName(name)).toBe(true),
  );

  it.each(['foo..bar', 'a..b', '..', '...', 'a..', '..b', '.hidden', 'a/b', '', 'with space'])(
    'rejects %s (path-traversal vector)',
    (name) => expect(isValidProfileName(name)).toBe(false),
  );

  it('rejects non-strings', () => {
    expect(isValidProfileName(undefined)).toBe(false);
    expect(isValidProfileName(null)).toBe(false);
    expect(isValidProfileName(42)).toBe(false);
  });
});

describe('RESERVED_PROFILE_NAMES', () => {
  it('mirrors the core contract (default + alpi)', () => {
    expect(RESERVED_PROFILE_NAMES).toEqual(['default', 'alpi']);
  });
});

describe('profileNameError', () => {
  it('returns null for empty input (no error before user types)', () => {
    expect(profileNameError('')).toBeNull();
  });

  it('flags bad format', () => {
    expect(profileNameError('.hidden')).toMatch(/start with/);
  });

  it('flags ".." anywhere inside the name (path-traversal vector)', () => {
    expect(profileNameError('foo..bar')).toMatch(/never contain/i);
  });

  it('flags reserved aliases', () => {
    expect(profileNameError('default')).toMatch(/reserved/);
    expect(profileNameError('alpi')).toMatch(/reserved/);
  });

  it('flags the mobile-only route conflict (new)', () => {
    expect(profileNameError('new')).toMatch(/route/);
  });

  it('flags duplicates', () => {
    expect(profileNameError('work', ['work', 'home'])).toMatch(/already exists/);
  });

  it('accepts a fresh valid name', () => {
    expect(profileNameError('work', ['home'])).toBeNull();
  });
});

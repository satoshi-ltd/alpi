import { describe, it, expect } from 'vitest';

import { nextSheetValue } from './sheet-value.js';

describe('nextSheetValue', () => {
  it('seeds on first open (prevInitial null) regardless of current', () => {
    expect(nextSheetValue({ current: '', newInitial: '/real/path', prevInitial: null })).toBe('/real/path');
    expect(nextSheetValue({ current: 'leftover', newInitial: '', prevInitial: null })).toBe('');
  });

  it('hydrates value when initialValue arrives async and the user has not typed', () => {
    expect(nextSheetValue({ current: '', newInitial: '/Users/javi/Documents/Obsidian', prevInitial: '' })).toBe('/Users/javi/Documents/Obsidian');
  });

  it('keeps the user input when initialValue updates after the user typed', () => {
    expect(nextSheetValue({ current: '/typed/by/user', newInitial: '/external/update', prevInitial: '' })).toBe('/typed/by/user');
  });

  it('after the user saved, future external updates flow through', () => {
    const saved = '/Users/javi/Documents/Obsidian';
    expect(nextSheetValue({ current: saved, newInitial: '/changed/elsewhere', prevInitial: saved })).toBe('/changed/elsewhere');
  });

  it('value already matches the new initialValue → idempotent', () => {
    expect(nextSheetValue({ current: '/same', newInitial: '/same', prevInitial: '/same' })).toBe('/same');
  });
});

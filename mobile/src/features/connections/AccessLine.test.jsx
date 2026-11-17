import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, testID, ...p }) => React.createElement('div', { ...p, 'data-testid': testID, 'data-justify': style?.justifyContent }, children);
  const Text = ({ children, style }) => React.createElement('span', { 'data-color': [].concat(style).reduce((c, s) => s?.color ?? c, null), 'data-strike': [].concat(style).some((s) => s?.textDecorationLine === 'line-through') ? '' : undefined }, children);
  return { View, Text };
});
vi.mock('../../components/Fold', () => ({ Fold: ({ shape, color }) => React.createElement('i', { 'data-shape': shape, 'data-color': color }) }));
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { bg: '#ffffff', ink: '#000000', ink2: '#333333', ink3: '#666666' }, fonts: { sans: { regular: 'r', medium: 'm' } }, fontSizes: { sm: 14 } }),
}));

const { AccessLine, accessLabel } = await import('./AccessLine');
const { nameTone } = await import('../../../../common/name.mjs');

const PROFILES = [
  { name: 'doc', accent: '#3899e2', shape: 'squircle' },
  { name: 'lingo', accent: '#9b5ad9', shape: 'clover' },
  { name: 'abby', accent: '#df4b9d', shape: 'drop' },
  { name: 'yuri', accent: '#f36a8a', shape: 'heart' },
];

const line = (row, extra) => render(<AccessLine row={row} profiles={PROFILES} {...extra} />).container;

describe('AccessLine', () => {
  it('reads All profiles for an admin and an empty scope', () => {
    expect(line({ role: 'admin', profile_scope: ['doc'] }).textContent).toBe('All profiles');
    expect(line({ role: 'member', profile_scope: [] }).textContent).toBe('All profiles');
    expect(accessLabel({ role: 'admin' }, PROFILES)).toBe('All profiles');
  });

  it('draws each profile as its mark and its name in its own tone, three at most, then +N', () => {
    const el = line({ role: 'member', profile_scope: ['doc', 'lingo', 'abby', 'yuri'] });
    expect([...el.querySelectorAll('[data-shape]')].map((m) => m.getAttribute('data-shape'))).toEqual(['squircle', 'clover', 'drop']);
    const names = [...el.querySelectorAll('span')].map((n) => [n.textContent, n.getAttribute('data-color')]);
    expect(names).toEqual([['doc', nameTone('#3899e2', '#ffffff')], ['lingo', nameTone('#9b5ad9', '#ffffff')], ['abby', nameTone('#df4b9d', '#ffffff')], ['+1', '#666666']]);
    expect(accessLabel({ role: 'member', profile_scope: ['doc', 'lingo', 'abby', 'yuri'] }, PROFILES)).toBe('doc, lingo, abby, yuri');
  });

  it('strikes a profile the roster no longer has, with no mark', () => {
    const el = line({ role: 'member', profile_scope: ['archive'] });
    expect(el.querySelector('[data-shape]')).toBeNull();
    expect(el.querySelector('[data-strike]').textContent).toBe('archive');
  });

  it('names the scope plainly, struck nowhere, until the roster has loaded, and speaks a removed profile', () => {
    const el = render(<AccessLine row={{ role: 'member', profile_scope: ['doc'] }} profiles={null} />).container;
    expect(el.textContent).toBe('doc');
    expect(el.querySelector('[data-strike]')).toBeNull();
    expect(el.querySelector('[data-shape]')).toBeNull();
    expect(accessLabel({ role: 'member', profile_scope: ['doc', 'archive'] }, PROFILES)).toBe('doc, archive (removed)');
  });

  it('aligns to the end when it sits in a value slot', () => {
    expect(line({ role: 'member', profile_scope: ['doc'] }, { align: 'flex-end' }).querySelector('[data-testid]').getAttribute('data-justify')).toBe('flex-end');
  });
});

import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ os: 'ios' }));

vi.mock('react-native', () => ({
  Platform: { get OS() { return h.os; } },
  ScrollView: ({ children }) => React.createElement('div', {}, children),
  Text: ({ children, selectable, style }) =>
    React.createElement('span', { 'data-selectable': String(!!selectable), 'data-size': style.fontSize }, children),
  TextInput: ({ value, editable, multiline, style }) =>
    React.createElement('textarea', { readOnly: editable === false, 'data-multiline': String(!!multiline), 'data-size': style.fontSize, value }),
}));
vi.mock('../../components/Sheet', () => ({
  Sheet: ({ open, title, children }) => (open ? React.createElement('section', { 'data-title': title }, children) : null),
}));
vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return { useTheme: () => ({ colors: tokens.palettes.light, fonts: tokens.fonts, fontSizes: tokens.fontSizes }) };
});

import { fontSizes, typography } from '../../theme/tokens';
import { SelectTextSheet } from './SelectTextSheet';

describe('SelectTextSheet', () => {
  it('shows the message in a read-only text view on iOS, which keeps range selection', () => {
    h.os = 'ios';
    const { container } = render(<SelectTextSheet text="alpha beta" />);
    const input = container.querySelector('textarea');
    expect(input.value).toBe('alpha beta');
    expect(input.readOnly).toBe(true);
    expect(Number(input.getAttribute('data-size'))).toBe(fontSizes[typography.chat.size]);
  });

  it('uses selectable text on Android', () => {
    h.os = 'android';
    render(<SelectTextSheet text="alpha beta" />);
    expect(screen.getByText('alpha beta').getAttribute('data-selectable')).toBe('true');
  });

  it('stays closed without text', () => {
    const { container } = render(<SelectTextSheet text={null} />);
    expect(container.textContent).toBe('');
  });
});

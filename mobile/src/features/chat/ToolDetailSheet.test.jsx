import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ copied: [], toasts: [] }));

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', {}, children);
  const Text = ({ children, selectable, style }) =>
    React.createElement('span', { 'data-selectable': selectable ? 'true' : undefined, 'data-font': style?.fontFamily }, children);
  return { View, Text, ScrollView: View };
});

vi.mock('../../components/Sheet', () => ({
  Sheet: ({ open, title, primaryAction, children }) =>
    open
      ? React.createElement(
          'section',
          { 'data-title': title },
          children,
          (primaryAction ?? []).map((a) => React.createElement('button', { key: a.id, type: 'button', onClick: a.onPress }, a.label)),
        )
      : null,
}));
vi.mock('../../components/Toast', () => ({ useToast: () => (t) => h.toasts.push(t) }));
vi.mock('../../lib/clipboard', () => ({ copyText: async (t) => { h.copied.push(t); return true; } }));
vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return { useTheme: () => ({ colors: tokens.palettes.light, fonts: tokens.fonts, fontSizes: tokens.fontSizes }) };
});

import { fonts } from '../../theme/tokens';
import { ToolDetailSheet } from './ToolDetailSheet';

describe('ToolDetailSheet', () => {
  it('shows full args as pretty mono JSON, the output, and the duration in the title', () => {
    render(<ToolDetailSheet tool={{ name: 'shell', args: { command: 'npm run lint --fix' }, ok: false, output: 'src/app.ts:14 no-unused-vars', duration_s: 4.1 }} status="error" />);
    expect(document.querySelector('[data-title]').getAttribute('data-title')).toBe('shell · failed in 4.1s');
    const args = screen.getByText(/"command": "npm run lint --fix"/);
    expect(args.getAttribute('data-selectable')).toBe('true');
    expect(args.getAttribute('data-font')).toBe(fonts.mono);
    expect(screen.getByText('src/app.ts:14 no-unused-vars').getAttribute('data-selectable')).toBe('true');
  });

  it('marks a truncated stored result as an excerpt', () => {
    render(<ToolDetailSheet tool={{ name: 'read_file', args: { path: 'a' }, ok: true, result: `${'x'.repeat(399)}…` }} status="success" />);
    expect(screen.getByText('excerpt')).toBeTruthy();
  });

  it('copies the output and the command', async () => {
    h.copied.length = 0;
    render(<ToolDetailSheet tool={{ name: 'terminal', args: { command: 'ls -la' }, ok: true, output: 'total 0' }} status="success" />);
    fireEvent.click(screen.getByText('Copy output'));
    fireEvent.click(screen.getByText('Copy command'));
    await waitFor(() => expect(h.copied).toEqual(['total 0', 'ls -la']));
  });

  it('offers the arguments when there is no command', () => {
    render(<ToolDetailSheet tool={{ name: 'read_file', args: { path: 'a' }, ok: null }} status="running" />);
    expect(screen.getByText('Copy arguments')).toBeTruthy();
    expect(screen.queryByText('Copy output')).toBeNull();
    expect(screen.getByText(/Still running/)).toBeTruthy();
  });

  it('renders nothing without a tool', () => {
    const { container } = render(<ToolDetailSheet tool={null} status="success" />);
    expect(container.textContent).toBe('');
  });
});

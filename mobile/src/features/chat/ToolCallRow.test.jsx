import React from 'react';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', { ...p, 'data-gap': style?.gap, 'data-indent': style?.paddingLeft }, children);
  const Text = ({ children, style, numberOfLines, ...p }) =>
    React.createElement('span', { ...p, 'data-font': style?.fontFamily, 'data-size': style?.fontSize, 'data-color': style?.color }, children);
  const Pressable = ({ children, onPress, accessibilityLabel, accessibilityState, style, accessibilityRole, hitSlop, ...p }) => {
    const resolved = typeof style === 'function' ? style({ pressed: false }) : style;
    return React.createElement(
      'button',
      { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'aria-expanded': accessibilityState?.expanded, 'data-min-h': resolved?.minHeight, 'data-slop': (hitSlop?.top ?? 0) + (hitSlop?.bottom ?? 0), ...p },
      children,
    );
  };
  const Animated = {
    View,
    Value: class { constructor(v) { this.v = v; } },
    timing: () => ({ start() {}, stop() {} }),
    loop: () => ({ start() { motion.loops += 1; }, stop() {} }),
    sequence: () => ({ start() {}, stop() {} }),
  };
  return { View, Text, Pressable, Animated };
});

vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: { ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', danger: '#f00', dangerText: '#c00' },
      fonts: { mono: 'm', monoMedium: 'mm', sans: { regular: 'r' } },
      fontSizes: tokens.fontSizes,
    }),
  };
});

vi.mock('../../components/Icon', () => ({
  Icon: ({ name }) => React.createElement('span', { 'data-icon': name }),
}));

const motion = vi.hoisted(() => ({ reduce: false, loops: 0 }));
vi.mock('../../lib/reduceMotion', () => ({ useReduceMotion: () => motion.reduce }));
vi.mock('./ToolDetailSheet', () => ({
  ToolDetailSheet: ({ tool, status }) =>
    tool ? React.createElement('div', { 'data-sheet': tool.name, 'data-status': status }) : null,
}));

import { ToolModule } from './ToolCallRow';
import { fontSizes, mobile } from '../../theme/tokens';
import { PROCESS_GAP, PROCESS_INDENT, PROCESS_ROW_H } from './processRow';

describe('ToolModule', () => {
  it('a single tool renders inline, no bucket', () => {
    render(<ToolModule tools={[{ name: 'read', args: { path: 'a' }, ok: true }]} accent="#0af" />);
    expect(screen.getByText('read')).toBeTruthy();
    expect(screen.queryByText(/tool calls?$/)).toBeNull();
  });

  it('finished tools collapse into the bucket and expand on tap', () => {
    render(<ToolModule tools={[
      { name: 'aaa', ok: true, tool_id: 't1' },
      { name: 'bbb', ok: true, tool_id: 't2' },
    ]} accent="#0af" />);
    expect(screen.getByText('2 tool calls')).toBeTruthy();
    expect(screen.queryByText('aaa')).toBeNull();
    fireEvent.click(screen.getByText('2 tool calls').closest('button'));
    expect(screen.getByText('aaa')).toBeTruthy();
    expect(screen.getByText('bbb')).toBeTruthy();
  });

  it('a running tool stays out of the previous bucket', () => {
    render(<ToolModule tools={[
      { name: 'aaa', ok: true, tool_id: 't1' },
      { name: 'bbb', ok: null, tool_id: 't2' },
    ]} accent="#0af" />);
    expect(screen.getByText('+1 previous tool call')).toBeTruthy();
    expect(screen.getByText('bbb')).toBeTruthy();
    expect(screen.queryByText('aaa')).toBeNull();
  });

  it('opens a bucket with a failure so the failed row is one tap away, and counts it once collapsed', () => {
    render(<ToolModule tools={[
      { name: 'aaa', ok: true, tool_id: 't1' },
      { name: 'bbb', ok: false, tool_id: 't2' },
    ]} accent="#0af" />);
    expect(screen.getByText('bbb')).toBeTruthy();
    fireEvent.click(screen.getByText('Hide tool calls').closest('button'));
    expect(screen.queryByText('bbb')).toBeNull();
    expect(screen.getByText('1 failed')).toBeTruthy();
  });
});

describe('tool rows open their detail', () => {
  it('shows a family icon and a plain summary on one compact row whose slop only meets its neighbours', () => {
    render(<ToolModule tools={[{ name: 'read_file', args: { path: 'deploy.log', limit: 200 }, ok: true }]} />);
    expect(document.querySelector('[data-icon="file"]')).toBeTruthy();
    expect(screen.getByText('deploy.log')).toBeTruthy();
    const row = screen.getByLabelText('read_file. Show details');
    expect(Number(row.getAttribute('data-min-h'))).toBe(PROCESS_ROW_H);
    expect(Number(row.getAttribute('data-slop'))).toBe(PROCESS_GAP);
  });

  it('sets names in ink-2 and labels in ink-3, all in the same mono size', () => {
    render(<ToolModule tools={[
      { name: 'read_file', args: { path: 'a.log' }, ok: true, tool_id: 't1' },
      { name: 'grep', args: { pattern: 'x' }, ok: true, tool_id: 't2' },
    ]} />);
    const label = screen.getByText('2 tool calls');
    expect(label.getAttribute('data-color')).toBe('#666');
    fireEvent.click(label.closest('button'));
    const name = screen.getByText('read_file');
    expect(name.getAttribute('data-color')).toBe('#333');
    expect(screen.getByText('a.log').getAttribute('data-color')).toBe('#666');
    for (const el of [label, name, screen.getByText('a.log')]) {
      expect(el.getAttribute('data-font')).toBe('m');
      expect(Number(el.getAttribute('data-size'))).toBe(fontSizes.sm);
    }
    expect(Number(name.closest('[data-indent]').getAttribute('data-indent'))).toBe(PROCESS_INDENT);
    expect(Number(document.querySelector('[data-gap]').getAttribute('data-gap'))).toBe(PROCESS_GAP);
  });

  it('opens the sheet for the tapped call, not its namesake', () => {
    render(<ToolModule tools={[
      { name: 'terminal', args: { command: 'ls' }, ok: true },
      { name: 'terminal', args: { command: 'npm test' }, ok: true },
    ]} />);
    fireEvent.click(screen.getByText('2 tool calls').closest('button'));
    expect(document.querySelector('[data-sheet]')).toBeNull();
    fireEvent.click(screen.getByText('npm test').closest('button'));
    expect(document.querySelector('[data-sheet="terminal"]')).toBeTruthy();
  });

  it('puts the failure inline and opens it in one tap', () => {
    render(<ToolModule tools={[{ name: 'shell', args: { command: 'npm run lint' }, ok: false, result: 'src/app.ts:14 no-unused-vars\n1 error' }]} />);
    expect(screen.getByText('src/app.ts:14 no-unused-vars')).toBeTruthy();
    expect(screen.queryByText('npm run lint')).toBeNull();
    fireEvent.click(screen.getByLabelText('shell, failed. Show details'));
    expect(document.querySelector('[data-sheet="shell"]').getAttribute('data-status')).toBe('error');
  });

  it('keeps the running pulse still under reduced motion', () => {
    motion.loops = 0;
    motion.reduce = true;
    render(<ToolModule tools={[{ name: 'web_fetch', args: { url: 'https://x' }, ok: null }]} />);
    expect(motion.loops).toBe(0);
    cleanup();
    motion.reduce = false;
    render(<ToolModule tools={[{ name: 'web_fetch', args: { url: 'https://x' }, ok: null }]} />);
    expect(motion.loops).toBe(1);
  });
});

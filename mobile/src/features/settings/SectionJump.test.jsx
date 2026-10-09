import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, renderHook, screen, act } from '@testing-library/react';

vi.mock('react-native', () => {
  const View = ({ children, accessibilityRole }) => React.createElement('div', { role: accessibilityRole }, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress, accessibilityLabel, accessibilityState, style }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'aria-selected': accessibilityState?.selected, 'data-minheight': String(style?.minHeight ?? 0) }, children);
  const ScrollView = ({ children }) => React.createElement('div', {}, children);
  return { View, Text, Pressable, ScrollView };
});
vi.mock('../../components/Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('h2', {}, children) }));
vi.mock('../../components/Icon', () => ({ Icon: () => null }));
vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: { bg: '#fff', hover: '#eee', line: '#ddd', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', selected: '#ddd', warning: '#e08a3c', warningText: '#8a5a0a', danger: '#c14545' },
      fonts: { sans: { regular: 'r', semibold: 's' }, mono: 'mono' },
      fontSizes: tokens.fontSizes,
    }),
  };
});

import { AttentionSummary, JumpChips } from './SectionJump';
import { JUMP_SECTIONS, sectionAt, summaryRows } from './jumpSections';
import { useSectionJump } from './useSectionJump';

afterEach(cleanup);

const ATT = {
  schedules: [{ id: 'j1' }],
  memory: [{ file: 'AGENT.md' }, { file: 'MEMORY.md' }],
  skills: [],
};

describe('attention summary rows', () => {
  it('names each flagged area once and says where it lives', () => {
    expect(summaryRows(ATT)).toEqual([
      { id: 'schedule', text: '1 job failed', section: 'schedule', label: 'Schedule' },
      { id: 'memory', text: '2 memory files at or over their limit', section: 'brain', label: 'Brain' },
    ]);
    expect(summaryRows({ skills: [{ name: 'a' }, { name: 'b' }], schedules: [{}, {}], memory: [{}] }).map((r) => r.text)).toEqual(['2 jobs failed', '1 memory file at or over its limit', '2 skills to fix']);
  });

  it('is empty with nothing flagged, with no attention and with an old daemon', () => {
    expect(summaryRows({ schedules: [], memory: [], skills: [] })).toEqual([]);
    expect(summaryRows(null)).toEqual([]);
    expect(summaryRows({})).toEqual([]);
  });
});

describe('attention summary card', () => {
  it('is absent while nothing is flagged', () => {
    const { container } = render(<AttentionSummary att={{ schedules: [], memory: [], skills: [] }} onJump={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it('counts the flagged areas and jumps to the section of the one tapped', () => {
    const onJump = vi.fn();
    render(<AttentionSummary att={ATT} onJump={onJump} />);
    expect(screen.getByText('Needs you · 2')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('1 job failed, Schedule'));
    fireEvent.click(screen.getByLabelText('2 memory files at or over their limit, Brain'));
    expect(onJump.mock.calls.map(([s]) => s)).toEqual(['schedule', 'brain']);
    for (const b of screen.getAllByRole('button')) expect(Number(b.getAttribute('data-minheight'))).toBeGreaterThanOrEqual(44);
  });
});

describe('section chips', () => {
  it('lists the sections in page order at the touch floor and marks the one in view', () => {
    const onJump = vi.fn();
    render(<JumpChips current="usage" onJump={onJump} />);
    const chips = screen.getAllByRole('button');
    expect(chips.map((c) => c.getAttribute('aria-label'))).toEqual(JUMP_SECTIONS.map((s) => `Go to ${s.label}`));
    expect(JUMP_SECTIONS.map((s) => s.id)).toEqual(['overview', 'usage', 'identity', 'service', 'alp', 'schedule', 'sandbox', 'voice', 'mcp', 'brain', 'storage']);
    for (const c of chips) expect(Number(c.getAttribute('data-minheight'))).toBeGreaterThanOrEqual(44);
    expect(screen.getByLabelText('Go to Usage').getAttribute('aria-selected')).toBe('true');
    expect(screen.getByLabelText('Go to Brain').getAttribute('aria-selected')).toBe('false');
    fireEvent.click(screen.getByLabelText('Go to Brain'));
    expect(onJump).toHaveBeenCalledWith('brain');
  });
});

describe('section position', () => {
  const OFFSETS = { overview: 40, usage: 900, identity: 1300, brain: 2600 };

  it('follows the last section whose header has reached the top', () => {
    expect(sectionAt(OFFSETS, 0)).toBe('overview');
    expect(sectionAt(OFFSETS, 890)).toBe('usage');
    expect(sectionAt(OFFSETS, 1400)).toBe('identity');
    expect(sectionAt(OFFSETS, 99999)).toBe('brain');
    expect(sectionAt({}, 500)).toBe('overview');
  });

  it('scrolls to a recorded header, a little above it, and ignores one it never measured', () => {
    const { result } = renderHook(() => useSectionJump());
    const scrollTo = vi.fn();
    result.current.scrollRef.current = { scrollTo };
    result.current.anchor('brain').onLayout({ nativeEvent: { layout: { y: 2600 } } });
    result.current.anchor('overview').onLayout({ nativeEvent: { layout: { y: 2 } } });
    result.current.jump('brain');
    expect(scrollTo).toHaveBeenCalledWith({ y: 2596, animated: true });
    result.current.jump('overview');
    expect(scrollTo).toHaveBeenLastCalledWith({ y: 0, animated: true });
    result.current.jump('storage');
    expect(scrollTo).toHaveBeenCalledTimes(2);
  });

  it('marks the section in view as the page scrolls', () => {
    const { result } = renderHook(() => useSectionJump());
    result.current.anchor('overview').onLayout({ nativeEvent: { layout: { y: 40 } } });
    result.current.anchor('usage').onLayout({ nativeEvent: { layout: { y: 900 } } });
    expect(result.current.section).toBe('overview');
    act(() => result.current.onScroll({ nativeEvent: { contentOffset: { y: 950 } } }));
    expect(result.current.section).toBe('usage');
  });
});

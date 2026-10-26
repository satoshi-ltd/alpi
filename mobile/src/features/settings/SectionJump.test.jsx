import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, renderHook, screen, act } from '@testing-library/react';

const h = vi.hoisted(() => ({ layouts: {}, scrolls: [], stripLayout: null, onScroll: null, onContent: null }));

vi.mock('react-native', () => {
  const View = ({ children, accessibilityRole }) => React.createElement('div', { role: accessibilityRole }, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress, onLayout, accessibilityLabel, accessibilityState, style }) => {
    if (onLayout) h.layouts[accessibilityLabel] = onLayout;
    return React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'aria-selected': accessibilityState?.selected, 'data-minheight': String(style?.minHeight ?? 0) }, children);
  };
  const ScrollView = React.forwardRef(({ children, onLayout, onScroll, onContentSizeChange }, ref) => {
    React.useImperativeHandle(ref, () => ({ scrollTo: (arg) => h.scrolls.push(arg) }));
    h.stripLayout = onLayout;
    h.onScroll = onScroll;
    h.onContent = onContentSizeChange;
    return React.createElement('div', {}, children);
  });
  return { View, Text, Pressable, ScrollView };
});
vi.mock('../../components/Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('h2', {}, children) }));
vi.mock('../../components/Icon', () => ({ Icon: () => null }));
vi.mock('../../components/EdgeFade', () => ({ EdgeFade: ({ side }) => React.createElement('i', { 'data-testid': `edge-fade-${side}` }) }));
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

import { AttentionSummary, JumpChips, chipScrollX } from './SectionJump';
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

describe('section chips edge fades', () => {
  const scrolled = (x, content = 900, view = 390) => act(() => h.onScroll({ nativeEvent: { contentOffset: { x }, contentSize: { width: content }, layoutMeasurement: { width: view } } }));

  it('fades the right edge while more chips are offscreen and the left once some are hidden', () => {
    render(<JumpChips current="overview" onJump={() => {}} />);
    act(() => h.stripLayout({ nativeEvent: { layout: { width: 390 } } }));
    act(() => h.onContent(900, 44));
    expect(screen.queryByTestId('edge-fade-left')).toBeNull();
    expect(screen.getByTestId('edge-fade-right')).toBeTruthy();
    scrolled(200);
    expect(screen.getByTestId('edge-fade-left')).toBeTruthy();
    expect(screen.getByTestId('edge-fade-right')).toBeTruthy();
    scrolled(510);
    expect(screen.getByTestId('edge-fade-left')).toBeTruthy();
    expect(screen.queryByTestId('edge-fade-right')).toBeNull();
  });

  it('recomputes the fades when the width arrives after the content, and when the view grows', () => {
    render(<JumpChips current="overview" onJump={() => {}} />);
    act(() => h.onContent(360, 44));
    act(() => h.stripLayout({ nativeEvent: { layout: { width: 390 } } }));
    expect(screen.queryByTestId('edge-fade-right')).toBeNull();
    act(() => h.onContent(900, 44));
    expect(screen.getByTestId('edge-fade-right')).toBeTruthy();
    act(() => h.stripLayout({ nativeEvent: { layout: { width: 1000 } } }));
    expect(screen.queryByTestId('edge-fade-right')).toBeNull();
  });

  it('keeps the left fade when the content size changes while the strip is scrolled', () => {
    render(<JumpChips current="overview" onJump={() => {}} />);
    act(() => h.stripLayout({ nativeEvent: { layout: { width: 390 } } }));
    act(() => h.onContent(900, 44));
    act(() => h.onScroll({ nativeEvent: { contentOffset: { x: 200 }, contentSize: { width: 900 }, layoutMeasurement: { width: 390 } } }));
    act(() => h.onContent(950, 44));
    expect(screen.getByTestId('edge-fade-left')).toBeTruthy();
  });

  it('shows no fade when every chip fits', () => {
    render(<JumpChips current="overview" onJump={() => {}} />);
    act(() => h.stripLayout({ nativeEvent: { layout: { width: 390 } } }));
    act(() => h.onContent(360, 44));
    expect(screen.queryByTestId('edge-fade-left')).toBeNull();
    expect(screen.queryByTestId('edge-fade-right')).toBeNull();
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
    act(() => result.current.jump('brain'));
    expect(scrollTo).toHaveBeenCalledWith({ y: 2596, animated: true });
    act(() => result.current.jump('overview'));
    expect(scrollTo).toHaveBeenLastCalledWith({ y: 0, animated: true });
    act(() => result.current.jump('storage'));
    expect(scrollTo).toHaveBeenCalledTimes(2);
  });

  it('marks the chip tapped at once and keeps it while the animated scroll reports stale offsets', () => {
    vi.useFakeTimers();
    try {
      const { result } = renderHook(() => useSectionJump());
      result.current.scrollRef.current = { scrollTo: vi.fn() };
      result.current.anchor('mcp').onLayout({ nativeEvent: { layout: { y: 2200 } } });
      result.current.anchor('brain').onLayout({ nativeEvent: { layout: { y: 2600 } } });
      act(() => result.current.jump('brain'));
      expect(result.current.section).toBe('brain');
      act(() => result.current.onScroll({ nativeEvent: { contentOffset: { y: 2300 } } }));
      expect(result.current.section).toBe('brain');
      act(() => { vi.advanceTimersByTime(1000); });
      act(() => result.current.onScroll({ nativeEvent: { contentOffset: { y: 2300 } } }));
      expect(result.current.section).toBe('mcp');
    } finally {
      vi.useRealTimers();
    }
  });

  it('follows the finger again as soon as the user drags during a jump', () => {
    const { result } = renderHook(() => useSectionJump());
    result.current.scrollRef.current = { scrollTo: vi.fn() };
    result.current.anchor('mcp').onLayout({ nativeEvent: { layout: { y: 2200 } } });
    result.current.anchor('brain').onLayout({ nativeEvent: { layout: { y: 2600 } } });
    act(() => result.current.jump('brain'));
    act(() => result.current.onScrollBeginDrag());
    act(() => result.current.onScroll({ nativeEvent: { contentOffset: { y: 2300 } } }));
    expect(result.current.section).toBe('mcp');
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

describe('chip strip follows the marked chip', () => {
  it('centres a chip in the strip and never scrolls before the start', () => {
    expect(chipScrollX({ x: 900, width: 100 }, 360)).toBe(770);
    expect(chipScrollX({ x: 20, width: 80 }, 360)).toBe(0);
    expect(chipScrollX(undefined, 360)).toBeNull();
    expect(chipScrollX({ x: 900, width: 100 }, 0)).toBeNull();
  });

  it('scrolls the strip to the newly marked chip, which would otherwise sit off screen', () => {
    h.scrolls.length = 0;
    const { rerender } = render(<JumpChips current="overview" onJump={() => {}} />);
    h.stripLayout({ nativeEvent: { layout: { width: 360 } } });
    h.layouts['Go to Brain']({ nativeEvent: { layout: { x: 1100, width: 90 } } });
    rerender(<JumpChips current="brain" onJump={() => {}} />);
    expect(h.scrolls.at(-1)).toEqual({ x: 965, animated: true });
  });
});

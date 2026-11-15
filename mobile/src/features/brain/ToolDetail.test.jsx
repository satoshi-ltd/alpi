import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

const h = vi.hoisted(() => ({ heads: [] }));

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', {}, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const ScrollView = ({ children }) => React.createElement('div', {}, children);
  return { View, Text, ScrollView };
});
vi.mock('../../components/DeadEnd', () => ({ DeadEnd: () => null }));
vi.mock('../../components/Pill', () => ({ Pill: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../../components/Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../../components/ScreenHeader', () => ({ ScreenHeader: () => null }));
vi.mock('../profile/PanelHeader', () => ({ PanelHeader: () => null }));
vi.mock('../../components/Busy', () => ({ Busy: () => null }));
vi.mock('../../components/SubtitleSkeleton', () => ({ SubtitleSkeleton: () => null }));
vi.mock('../../components/FactTable', () => ({ FactTable: () => null }));
vi.mock('../../components/DetailHead', () => ({ DetailHead: (props) => { h.heads.push(props); return null; } }));
vi.mock('../../hooks/useBusyVisible', () => ({ useBusyVisible: () => false }));
vi.mock('../../hooks/useDaemonData', () => ({
  useTools: () => ({ data: { tools: [{ name: 'web_fetch', category: 'Web', description: 'Fetches a page.', parameters: {} }] }, loading: false }),
}));
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: {}, fonts: { sans: { regular: 'r', medium: 'm' }, mono: { regular: 'mono', medium: 'mono' } }, fontSizes: { sm: 13, md: 15 } }),
}));

import { ToolDetail } from './ToolDetail';

afterEach(() => {
  cleanup();
  h.heads.length = 0;
});

describe('tool detail', () => {
  it('shows and copies the real tool name, not a made-up category path', () => {
    render(<ToolDetail profile="scout" name="web_fetch" />);
    expect(h.heads.at(-1)).toMatchObject({ title: 'web_fetch', id: 'web_fetch' });
  });
});

import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ params: {}, call: null }));

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', {}, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  return { View, Text, ScrollView: View };
});
vi.mock('expo-router', () => ({ useLocalSearchParams: () => h.params }));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/theme/ThemeContext', async () => {
  const tokens = await import('../src/theme/tokens');
  return { useTheme: () => ({ colors: new Proxy({}, { get: () => '#000' }), fonts: tokens.fonts, fontSizes: tokens.fontSizes }) };
});
vi.mock('../src/components/RichText', () => ({ RichText: ({ children }) => React.createElement('article', {}, children) }));
vi.mock('../src/components/ReaderSkeleton', () => ({ ReaderSkeleton: ({ label }) => React.createElement('p', {}, label) }));
vi.mock('../src/features/profile/PanelHeader', () => ({ PanelHeader: ({ section }) => React.createElement('header', {}, section) }));
vi.mock('../src/hooks/useBack', () => ({ useBack: () => () => {} }));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ call: h.call }) }));

import SkillFile from '../app/profile/[id]/brain/skill-file.jsx';

describe('a skill file', () => {
  it('opens with its name, size and body', async () => {
    h.params = { id: 'doc', name: 'brief-writer', category: 'writing', file: 'SKILL.md' };
    h.call = vi.fn(async () => ({ file: { size: 2048, ftype: 'skill', binary: false, truncated: false, text: '# Brief writer' } }));
    render(<SkillFile />);
    expect(await screen.findByText('# Brief writer')).toBeTruthy();
    expect(screen.getByText('SKILL.md')).toBeTruthy();
    expect(screen.getByText('2.0 KB')).toBeTruthy();
    expect(h.call).toHaveBeenCalledWith('host.skill.file', { profile: 'doc', name: 'brief-writer', category: 'writing', path: 'SKILL.md' });
  });

  it('marks a truncated file beside its size', async () => {
    h.params = { id: 'doc', name: 'brief-writer', file: 'scripts/run.py' };
    h.call = vi.fn(async () => ({ file: { size: 10, ftype: 'py', binary: false, truncated: true, text: 'print(1)' } }));
    render(<SkillFile />);
    expect(await screen.findByText('10 B · truncated')).toBeTruthy();
  });
});

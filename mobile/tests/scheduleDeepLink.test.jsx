import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  params: { id: 'abby', job: 'j-mail' },
  jobs: [
    { id: 'j-first', kind: 'cron', expression: '0 6 * * *', prompt: 'first prompt', title: 'First' },
    { id: 'j-mail', kind: 'cron', expression: '0 7 * * *', prompt: 'mail prompt', title: 'Mail' },
  ],
}));

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', {}, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, children);
  return {
    View, Text, Pressable,
    ScrollView: ({ children }) => React.createElement('div', {}, children),
    RefreshControl: () => null,
    ActivityIndicator: () => null,
  };
});
vi.mock('expo-router', () => ({ useLocalSearchParams: () => h.params }));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { bg: '#fff', ink: '#000', ink2: '#333', ink3: '#666', danger: '#f00' }, fonts: { sans: { regular: 'r', semibold: 's' }, mono: 'm' }, fontSizes: { xs: 11, sm: 12, md: 13, lg: 15 } }),
}));
vi.mock('../src/components/ActionSheet', () => ({
  ActionSheet: ({ open, subtitle }) => (open ? React.createElement('div', { 'data-sheet': subtitle }) : null),
}));
vi.mock('../src/components/Icon', () => ({ Icon: () => null }));
vi.mock('../src/components/Row', () => ({
  Row: ({ title }) => React.createElement('div', {}, title),
  RowGroup: ({ children }) => React.createElement('div', {}, children),
  RowSeparator: () => null,
}));
vi.mock('../src/components/ScreenHeader', () => ({ ScreenHeader: () => null }));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../src/components/TypedConfirm', () => ({ Bold: () => null, Code: () => null, TypedConfirm: () => null }));
vi.mock('../src/hooks/useBack', () => ({ useBack: () => vi.fn() }));
vi.mock('../src/hooks/useDaemonData', () => ({ useScheduleList: () => ({ data: { jobs: h.jobs }, refresh: vi.fn() }) }));
vi.mock('../src/hooks/usePullRefresh', () => ({ usePullRefresh: () => ({}) }));
vi.mock('../src/hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ call: vi.fn() }) }));

import ScheduleList from '../app/profile/[id]/schedule/index.jsx';

describe('schedule screen opened from a notification', () => {
  it('opens the actions of the job the notification named', () => {
    const { container } = render(<ScheduleList />);
    expect(container.querySelector('[data-sheet]').getAttribute('data-sheet')).toBe('j-mail');
  });

  it('opens nothing when the job is gone', () => {
    h.params = { id: 'abby', job: 'j-deleted' };
    const { container } = render(<ScheduleList />);
    expect(container.querySelector('[data-sheet]')).toBeNull();
  });
});

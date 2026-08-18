import React from 'react';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  pathname: '/',
  canAdmin: true,
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(async () => {}),
}));

vi.mock('expo-router', () => ({
  useRouter: () => ({ push: h.push, replace: h.replace }),
  usePathname: () => h.pathname,
  useFocusEffect: (cb) => React.useEffect(() => cb(), [cb]),
}));

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children }) => React.createElement('div', {}, children),
}));

vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', bgSide: '#f5f6f8', ink: '#000', ink2: '#333', ink3: '#666', line: '#eee' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono', monoMedium: 'monoMedium' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15 },
  }),
}));

vi.mock('../src/components/Banner', () => ({ Banner: () => null }));
vi.mock('../src/features/inbox/ConnHeader', () => ({ ConnHeader: () => null }));
vi.mock('../src/features/shell/ShellFooter', () => ({
  ShellFooter: ({ onSettingsPress }) =>
    React.createElement('button', { type: 'button', 'aria-label': 'Settings', onClick: onSettingsPress }),
}));
vi.mock('../src/features/inbox/InboxRow', () => ({ InboxRow: () => null }));
vi.mock('../src/features/inbox/Roster', () => ({ Roster: () => null }));
vi.mock('../src/features/inbox/RowContextSheet', () => ({ RowContextSheet: () => null }));
vi.mock('../src/features/sheets/ConnectionSheet', () => ({ ConnectionSheet: () => null }));
vi.mock('../src/features/sheets/CreateProfileSheet', () => ({ CreateProfileSheet: () => null }));
vi.mock('../src/features/sheets/CreateWorkgroupSheet', () => ({ CreateWorkgroupSheet: () => null }));
vi.mock('../src/features/shell/HomePane', () => ({
  HomePane: () => React.createElement('div', { 'data-home': 'true' }),
}));

vi.mock('../src/hooks/useActiveRole', () => ({
  useCanAdminEarly: () => h.canAdmin,
  useIsAdmin: () => h.canAdmin,
}));
vi.mock('../src/hooks/useDebouncedCallback', () => ({ useDebouncedCallback: (fn) => fn }));
vi.mock('../src/hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../src/hooks/useInbox', () => ({
  useInbox: () => ({ items: [], loading: false, refresh: h.refresh }),
}));
vi.mock('../src/hooks/useUnifiedOutputs', () => ({ useUnifiedOutputs: () => ({ rows: [] }) }));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({
    endpoint: { id: 'c1', name: 'casa', url: 'http://casa' },
    probeState: new Map([['c1', 'online']]),
  }),
}));
vi.mock('../src/lib/pins', () => ({
  usePins: () => ({
    isProfilePinned: () => false,
    isWorkgroupPinned: () => false,
    toggleProfile: () => {},
    toggleWorkgroup: () => {},
  }),
}));
vi.mock('../src/lib/useFireOnce', () => ({ useFireOnce: () => {} }));

import { PaneContext } from '../src/nav/PaneContext';
import { SidebarPane } from '../src/features/shell/SidebarPane';
import Index from '../app/index.jsx';

function phone() {
  render(<Index />);
}

function tablet() {
  render(
    <PaneContext.Provider value={{ twoPane: true, side: 'list' }}>
      <SidebarPane />
    </PaneContext.Provider>,
  );
}

function pressSettings() {
  fireEvent.click(screen.getByLabelText('Settings'));
}

function anySheet() {
  return document.querySelector('[data-sheet]');
}

beforeEach(() => {
  h.pathname = '/';
  h.canAdmin = true;
  h.push.mockClear();
  h.replace.mockClear();
});

describe('settings entry · phone', () => {
  it('pushes the settings route instead of opening a sheet', () => {
    phone();
    pressSettings();
    expect(h.push).toHaveBeenCalledWith('/settings');
    expect(h.replace).not.toHaveBeenCalled();
    expect(anySheet()).toBeNull();
  });

  it('sends a member to the same route', () => {
    h.canAdmin = false;
    phone();
    pressSettings();
    expect(h.push).toHaveBeenCalledWith('/settings');
    expect(anySheet()).toBeNull();
  });

  it('hands the tablet to the home pane, so the sidebar footer owns settings there', () => {
    render(
      <PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>
        <Index />
      </PaneContext.Provider>,
    );
    expect(document.querySelector('[data-home="true"]')).toBeTruthy();
    expect(screen.queryByLabelText('Settings')).toBeNull();
  });
});

describe('settings entry · tablet', () => {
  it('replaces the detail pane from another pane root', () => {
    h.pathname = '/chat/doc';
    tablet();
    pressSettings();
    expect(h.replace).toHaveBeenCalledWith('/settings');
    expect(h.push).not.toHaveBeenCalled();
    expect(anySheet()).toBeNull();
  });

  it('pushes from a drilled screen so its back stack survives', () => {
    h.pathname = '/wg/alpha/settings';
    tablet();
    pressSettings();
    expect(h.push).toHaveBeenCalledWith('/settings');
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('sends a member to the same route', () => {
    h.canAdmin = false;
    tablet();
    pressSettings();
    expect(h.replace).toHaveBeenCalledWith('/settings');
    expect(anySheet()).toBeNull();
  });
});

const ROOT = join(import.meta.dirname, '..');

describe('one settings destination', () => {
  it.each(['app/index.jsx', 'src/features/shell/SidebarPane.jsx'])(
    '%s opens the shared route through openVerb, with no sheet fallback',
    (path) => {
      const source = readFileSync(join(ROOT, path), 'utf8');
      expect(source).toMatch(/openVerb\(\{ twoPane[^)]*\}\)\]\(SETTINGS_PATH\)/);
      expect(source).not.toContain('SettingsSheet');
      expect(source).not.toMatch(/['"]\/settings['"]/);
    },
  );

  it('keeps no settings sheet in the tree', () => {
    expect(existsSync(join(ROOT, 'src/features/sheets/SettingsSheet.jsx'))).toBe(false);
  });
});

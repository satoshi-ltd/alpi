import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  pathname: '/',
  profiles: [],
  refresh: vi.fn(async () => {}),
  create: vi.fn(async () => 'ollama/llama3'),
  toast: vi.fn(),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, style, hitSlop, accessibilityLabel, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel },
      typeof children === 'function' ? children({ pressed: false }) : children,
    );
  const TextInput = ({ value, onChangeText, placeholder }) =>
    React.createElement('input', {
      value: value ?? '',
      placeholder,
      onChange: (e) => onChangeText?.(e.target.value),
    });
  const ScrollView = ({ children }) => React.createElement('div', {}, children);
  const Modal = ({ children, visible }) => (visible ? React.createElement('div', {}, children) : null);
  return { Keyboard: { addListener: () => ({ remove: () => {} }) }, Modal, Pressable, ScrollView, Text, TextInput, View, useWindowDimensions: () => ({ width: 390, height: 844 }) };
});

vi.mock('react-native-reanimated', () => ({
  default: {
    View: ({ children, style }) =>
      React.createElement('div', { 'data-style': JSON.stringify(Object.assign({}, ...[].concat(style))) }, children),
  },
}));
vi.mock('react-native-gesture-handler', () => ({
  GestureDetector: ({ children }) => React.createElement('div', {}, children),
}));
vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ bottom: 0 }) }));
vi.mock('../../components/useSheetGesture', () => ({
  useSheetGesture: (open) => ({ gesture: {}, sheetStyle: {}, backdropStyle: {}, mounted: open }),
}));
vi.mock('../../components/Button', () => ({
  Button: ({ title, onPress, disabled }) =>
    React.createElement('button', { type: 'button', onClick: onPress, disabled: !!disabled }, title),
}));
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: {
      bgPane: '#ffffff', bgInput: '#f1f3f5', line2: '#dddddd', hover: '#f4f4f4', selected: '#eaeaea',
      ink: '#0b1117', ink2: '#3d4955', ink3: '#7c8896', ink4: '#b1bac4',
      success: '#3fb37a', warning: '#d4b443', danger: '#c14545',
    },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15, xl: 18 },
    mobile: { inputH: 44 },
    shadow: { base: {} },
  }),
}));

vi.mock('expo-router', () => ({
  useRouter: () => ({ push: h.push, replace: h.replace }),
  usePathname: () => h.pathname,
}));
vi.mock('../../components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../../hooks/useDaemonData', () => ({
  useProfileSummaries: () => ({ data: { profiles: h.profiles }, loading: false, refresh: h.refresh }),
}));
vi.mock('../../lib/EndpointContext', () => ({ useEndpoint: () => ({ call: vi.fn(async () => ({})) }) }));
vi.mock('../../lib/createProfile', () => ({ createProfileWithProvider: h.create }));

import { PaneContext } from '../../nav/PaneContext';
import { CreateProfileSheet } from './CreateProfileSheet';

const NAME = 'work · personal · home-server';

function renderSheet(twoPane = false) {
  return render(
    <PaneContext.Provider value={{ twoPane, side: twoPane ? 'detail' : 'full' }}>
      <CreateProfileSheet open onClose={h.close} />
    </PaneContext.Provider>,
  );
}

const createButton = () => screen.getByRole('button', { name: 'Create' });
const sheetStyle = (container) =>
  JSON.parse([...container.querySelectorAll('[data-style]')].at(-1).getAttribute('data-style'));

beforeEach(() => {
  h.pathname = '/';
  h.profiles = [{ name: 'doc' }];
  h.push.mockClear();
  h.replace.mockClear();
  h.refresh.mockClear();
  h.create.mockClear();
  h.toast.mockClear();
  h.close = vi.fn();
});

describe('CreateProfileSheet validation', () => {
  it('keeps Create disabled until the name is valid', () => {
    renderSheet();
    expect(createButton().disabled).toBe(true);

    fireEvent.change(screen.getByPlaceholderText(NAME), { target: { value: 'mira' } });
    expect(createButton().disabled).toBe(false);
  });

  it('refuses a name that already exists', () => {
    renderSheet();
    fireEvent.change(screen.getByPlaceholderText(NAME), { target: { value: 'doc' } });
    expect(screen.getByText('@doc already exists')).toBeTruthy();
    expect(createButton().disabled).toBe(true);
  });

  it('refuses a reserved name', () => {
    renderSheet();
    fireEvent.change(screen.getByPlaceholderText(NAME), { target: { value: 'default' } });
    expect(screen.getByText('default is reserved')).toBeTruthy();
    expect(createButton().disabled).toBe(true);
  });

  it('masks characters a profile name can never hold', () => {
    renderSheet();
    fireEvent.change(screen.getByPlaceholderText(NAME), { target: { value: 'My Team!' } });
    expect(screen.getByPlaceholderText(NAME).value).toBe('myteam');
  });

  it('swaps the Ollama pair for an API key when a paid provider is picked', () => {
    renderSheet();
    fireEvent.change(screen.getByPlaceholderText(NAME), { target: { value: 'mira' } });
    fireEvent.click(screen.getByLabelText('Anthropic'));

    expect(screen.queryByPlaceholderText('local · home-gpu')).toBeNull();
    expect(createButton().disabled).toBe(true);

    fireEvent.change(screen.getByPlaceholderText('sk-ant-…'), { target: { value: 'sk-ant-x' } });
    expect(createButton().disabled).toBe(false);
  });

  it('also demands an initial model on OpenRouter', () => {
    renderSheet();
    fireEvent.change(screen.getByPlaceholderText(NAME), { target: { value: 'mira' } });
    fireEvent.click(screen.getByLabelText('OpenRouter'));
    fireEvent.change(screen.getByPlaceholderText('sk-or-…'), { target: { value: 'sk-or-x' } });
    expect(createButton().disabled).toBe(true);

    fireEvent.change(screen.getByPlaceholderText('anthropic/claude-sonnet-4.5'), {
      target: { value: 'anthropic/claude-sonnet-4.5' },
    });
    expect(createButton().disabled).toBe(false);
  });
});

describe('CreateProfileSheet creation', () => {
  it('creates with the picked provider, closes, then opens the new settings screen', async () => {
    renderSheet();
    fireEvent.change(screen.getByPlaceholderText(NAME), { target: { value: 'mira' } });
    fireEvent.click(createButton());

    await waitFor(() => expect(h.create).toHaveBeenCalled());
    expect(h.create.mock.calls[0][1]).toEqual({
      name: 'mira',
      providerId: 'ollama',
      env: undefined,
      apiKey: '',
      ollamaName: 'local',
      ollamaUrl: 'http://localhost:11434',
      openrouterModel: '',
    });
    await waitFor(() => expect(h.push).toHaveBeenCalledWith('/profile/mira/settings'));
    expect(h.refresh).toHaveBeenCalled();
    expect(h.close).toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('replaces instead of stacking when two panes sit on the list root', async () => {
    h.pathname = '/';
    renderSheet(true);
    fireEvent.change(screen.getByPlaceholderText(NAME), { target: { value: 'mira' } });
    fireEvent.click(createButton());

    await waitFor(() => expect(h.replace).toHaveBeenCalledWith('/profile/mira/settings'));
    expect(h.push).not.toHaveBeenCalled();
  });

  it('leaves the sheet usable when the daemon rejects the create', async () => {
    h.create.mockRejectedValueOnce(new Error('nope'));
    renderSheet();
    fireEvent.change(screen.getByPlaceholderText(NAME), { target: { value: 'mira' } });
    fireEvent.click(createButton());

    await waitFor(() => expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Create failed' })));
    expect(h.push).not.toHaveBeenCalled();
    expect(h.close).not.toHaveBeenCalled();
    await waitFor(() => expect(createButton().disabled).toBe(false));
  });
});

describe('CreateProfileSheet pane modes', () => {
  it('rides the phone bottom sheet on one pane', () => {
    const { container } = renderSheet();
    expect(sheetStyle(container).maxWidth).toBeUndefined();
    expect(screen.getByPlaceholderText(NAME)).toBeTruthy();
  });

  it('becomes a centred capped dialog on two panes', () => {
    const { container } = renderSheet(true);
    expect(sheetStyle(container).maxWidth).toBe(560);
    expect(screen.getByPlaceholderText(NAME)).toBeTruthy();
  });
});

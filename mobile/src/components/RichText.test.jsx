import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

const h = vi.hoisted(() => ({
  fontOf: (style) => [style].flat(Infinity).filter(Boolean).reduce((f, s) => s.fontFamily ?? f, null),
  uri: null,
}));

afterEach(() => {
  h.uri = null;
  cleanup();
});

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) =>
    React.createElement('span', { ...p, 'data-font': h.fontOf(style) }, children);
  const Pressable = ({ children, onPress, accessibilityLabel, accessibilityHint, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'data-hint': accessibilityHint },
      children,
    );
  const Image = (p) => React.createElement('img', { alt: p.accessibilityLabel });
  Image.getSize = () => {};
  return {
    View,
    Text,
    Pressable,
    Image,
    ScrollView: ({ children, ...p }) => React.createElement('div', {}, children),
    Modal: ({ children, visible, supportedOrientations }) =>
      visible
        ? React.createElement('div', { 'data-orientations': (supportedOrientations ?? []).join(',') }, children)
        : null,
    ActivityIndicator: () => React.createElement('span', { 'data-testid': 'spinner' }),
  };
});

vi.mock('../theme/ThemeContext', async () => {
  const tokens = await import('../theme/tokens');
  return {
    useTheme: () => ({
      colors: { ink: '#000', ink2: '#333', ink3: '#666', line: '#ddd', hover: '#eee' },
      fonts: {
        sans: { regular: 'Inter_400Regular', semibold: 'Inter_600SemiBold' },
        mono: 'JetBrainsMono_400Regular',
      },
      fontSizes: tokens.fontSizes,
    }),
  };
});

vi.mock('../lib/EndpointContext', () => ({ useEndpoint: () => ({ call: vi.fn(), endpoint: { id: 'c1' } }) }));
vi.mock('../hooks/useCachedImage', () => ({ useCachedImage: () => ({ uri: h.uri, err: null }) }));

import { RichText } from './RichText';

describe('RichText typography', () => {
  it('renders paragraphs, headings and list bullets in a theme font', () => {
    render(<RichText>{'# Title\n\n- first\n- second'}</RichText>);
    expect(screen.getByText('Title').closest('[data-font]').getAttribute('data-font')).toBe('Inter_600SemiBold');
    for (const bullet of screen.getAllByText('•')) {
      expect(bullet.getAttribute('data-font')).toBe('Inter_400Regular');
    }
  });

  it('renders a quote in a theme font', () => {
    render(<RichText>{'> quoted line'}</RichText>);
    expect(screen.getByText('quoted line').closest('[data-font]').getAttribute('data-font')).toBe('Inter_400Regular');
  });
});

describe('RichText image viewer', () => {
  it('lets the device rotate while the fullscreen image is open', () => {
    h.uri = 'file:///cache/room.png';
    const { container } = render(<RichText>{'![a room](/tmp/room.png "generated")'}</RichText>);
    expect(container.querySelector('[data-orientations]')).toBeNull();
    fireEvent.click(screen.getByRole('button'));
    expect(container.querySelector('[data-orientations]').getAttribute('data-orientations')).toBe(
      'portrait,landscape-left,landscape-right',
    );
  });
});

describe('RichText image viewer dismissal', () => {
  const openViewer = () => {
    h.uri = 'file:///cache/room.png';
    const view = render(<RichText>{'![a room](/tmp/room.png "generated")'}</RichText>);
    fireEvent.click(screen.getByRole('button'));
    return view;
  };

  it('offers the same labelled icon close as every sheet', () => {
    openViewer();
    const close = screen.getByRole('button', { name: 'Close' });
    expect(close).toBeTruthy();
    expect(close.getAttribute('data-hint')).toMatch(/backdrop/i);
  });

  it('shuts the viewer from the icon, not only from a backdrop tap nobody can see', () => {
    const { container } = openViewer();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(container.querySelector('[data-orientations]')).toBeNull();
  });
});

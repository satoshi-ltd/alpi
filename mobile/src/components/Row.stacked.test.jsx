import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ width: 390 }));

vi.mock('react-native', () => {
  const View = ({ children, style, onLayout, ...p }) => {
    React.useEffect(() => {
      onLayout?.({ nativeEvent: { layout: { width: h.width } } });
    }, [onLayout]);
    return React.createElement('div', { ...p, 'data-dir': style?.flexDirection ?? '', 'data-minh': style?.minHeight ?? '' }, children);
  };
  const Text = ({ children, style, numberOfLines, ellipsizeMode, ...p }) =>
    React.createElement('span', { ...p, 'data-ellipsis': ellipsizeMode ?? '', 'data-align': style?.textAlign ?? '', 'data-transform': style?.textTransform ?? '' }, children);
  const Pressable = ({ children, onPress, android_ripple, style, accessibilityLabel, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, ...p }, children);
  return { View, Text, Pressable };
});

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink2: '#222', ink3: '#666', ink4: '#999', danger: '#f00', bgPane: '#fff', selected: '#eee' },
    fonts: { sans: { regular: 'sans' }, mono: 'mono', monoMedium: 'monoMedium', monoSemibold: 'monoSemibold' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15, xl: 18 },
  }),
}));

import { PaneContext } from '../nav/PaneContext';
import { SettingsSurface } from '../nav/SettingsSurface';
import { Row, RowSeparator, SectionHeader } from './Row';

beforeEach(() => {
  h.width = 390;
});

describe('Row on a narrow cover screen', () => {
  it('keeps the value beside the label on a phone', () => {
    render(<Row label="Model" value="z-ai/glm-5.3-flash" onPress={() => {}} />);
    const value = screen.getByText('z-ai/glm-5.3-flash');
    expect(value.getAttribute('data-ellipsis')).toBe('middle');
    expect(value.getAttribute('data-align')).toBe('right');
  });

  it('drops the value under the label at full width below 360', () => {
    h.width = 344;
    render(<Row label="Model" helper="main model" value="z-ai/glm-5.3-flash" onPress={() => {}} />);
    const value = screen.getByText('z-ai/glm-5.3-flash');
    expect(value.getAttribute('data-ellipsis')).toBe('tail');
    expect(value.getAttribute('data-align')).toBe('left');
    expect(screen.getByText('main model')).toBeTruthy();
  });
});

describe('Row inside wide settings', () => {
  function wide(node) {
    return render(
      <PaneContext.Provider value={{ twoPane: true, side: 'detail', sidebarOpen: true, toggleSidebar: () => {} }}>
        <SettingsSurface>{node}</SettingsSurface>
      </PaneContext.Provider>,
    );
  }

  it('stands every wide row at least one 44 pt touch target tall and speaks it as one button', () => {
    wide(<Row label="Workspace" helper="where files land" value="~/git/casa/doc" onPress={() => {}} />);
    const button = screen.getByLabelText('Workspace, ~/git/casa/doc, where files land');
    expect(button.getAttribute('accessibilityRole')).toBe('button');
    expect(Number(button.querySelector('[data-minh]:not([data-minh=""])').getAttribute('data-minh'))).toBe(44);
  });

  it('renders the desktop field grid: label column, helper under it, mono value', () => {
    wide(<Row label="Workspace" helper="where files land" value="~/git/casa/doc" onPress={() => {}} />);
    const value = screen.getByText('~/git/casa/doc');
    expect(value.getAttribute('data-ellipsis')).toBe('middle');
    expect(screen.getByText('Workspace')).toBeTruthy();
    expect(screen.getByText('where files land')).toBeTruthy();
  });

  it('drops the row separators and gives section headers a kicker', () => {
    const { container } = wide(
      <>
        <SectionHeader kicker="last 14 days">Usage</SectionHeader>
        <RowSeparator />
      </>,
    );
    expect(screen.getByText('Usage')).toBeTruthy();
    expect(screen.getByText('last 14 days')).toBeTruthy();
    expect(container.querySelectorAll('div').length).toBeLessThan(4);
  });

  it('keeps the phone rows outside a settings surface even on a tablet', () => {
    render(
      <PaneContext.Provider value={{ twoPane: true, side: 'detail', sidebarOpen: true, toggleSidebar: () => {} }}>
        <Row label="Peers" value="3" onPress={() => {}} />
      </PaneContext.Provider>,
    );
    expect(screen.getByText('3').getAttribute('data-align')).toBe('right');
  });
});

describe('Row as an entity on a wide settings surface', () => {
  function wide(node) {
    return render(
      <PaneContext.Provider value={{ twoPane: true, side: 'detail', sidebarOpen: true, toggleSidebar() {} }}>
        <SettingsSurface>{node}</SettingsSurface>
      </PaneContext.Provider>,
    );
  }

  it('keeps an entity name in its own case, like the desktop table, instead of the field eyebrow', () => {
    wide(<Row label="emulator-android" helper="admin · 2 devices" item onPress={() => {}} />);
    expect(screen.getByText('emulator-android').getAttribute('data-transform')).toBe('');
  });

  it('still sets a field label as an eyebrow', () => {
    wide(<Row label="Public key" value="abc" />);
    expect(screen.getByText('Public key').getAttribute('data-transform')).toBe('uppercase');
  });
});

describe('Row chevron gutter on a wide settings surface', () => {
  function wide(node) {
    return render(
      <PaneContext.Provider value={{ twoPane: true, side: 'detail', sidebarOpen: true, toggleSidebar() {} }}>
        <SettingsSurface>{node}</SettingsSurface>
      </PaneContext.Provider>,
    );
  }

  it('reserves the gutter on a plain value row so it shares the right edge with chevron rows', () => {
    wide(<Row label="Port" value="7423" chevron={false} />);
    const value = screen.getByText('7423');
    expect(value.nextSibling).not.toBeNull();
    expect(value.nextSibling.tagName).toBe('DIV');
  });

  it('gives a row whose trailing control is the action no gutter, so the control sits on that same edge', () => {
    wide(<Row label="Pixel" helper="mobile" item trailing={<button type="button">revoke</button>} chevron={false} />);
    expect(screen.getByText('revoke').nextSibling).toBeNull();
  });
});

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
    return React.createElement('div', { ...p, 'data-dir': style?.flexDirection ?? '', 'data-minh': style?.minHeight ?? '', 'data-opacity': style?.opacity ?? '' }, children);
  };
  const Text = ({ children, style, numberOfLines, ellipsizeMode, ...p }) =>
    React.createElement('span', { ...p, 'data-ellipsis': ellipsizeMode ?? '', 'data-align': style?.textAlign ?? '', 'data-transform': style?.textTransform ?? '', 'data-color': style?.color ?? '' }, children);
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

describe('Row on a fold pane', () => {
  const inFold = (node) =>
    render(
      <PaneContext.Provider value={{ twoPane: true, side: 'detail', sidebarOpen: true, toggleSidebar: () => {} }}>
        {node}
      </PaneContext.Provider>,
    );

  it('draws the phone row: value right aligned beside the label, no uppercase label column', () => {
    inFold(<Row label="Workspace" helper="where files land" value="~/git/casa/doc" onPress={() => {}} />);
    expect(screen.getByText('~/git/casa/doc').getAttribute('data-align')).toBe('right');
    expect(screen.getByText('Workspace').getAttribute('data-transform')).toBe('');
  });

  it('keeps the section header on the phone eyebrow with the kicker joined', () => {
    inFold(<SectionHeader kicker="last 14 days">Usage</SectionHeader>);
    expect(screen.getByText('Usage · last 14 days')).toBeTruthy();
  });

  it('keeps the separator hairline', () => {
    const { container } = inFold(<RowSeparator />);
    expect(container.querySelectorAll('div').length).toBe(1);
  });
});

describe('Row text ink', () => {
  it('draws the helper in the secondary ink', () => {
    render(<Row label="Workspace" helper="where files land" value="~/git" onPress={() => {}} />);
    expect(screen.getByText('where files land').getAttribute('data-color')).toBe('#666');
  });

  it('marks a disabled row with the secondary ink instead of fading the whole row', () => {
    const { container } = render(<Row label="Terminal" helper="off" disabled />);
    expect(screen.getByText('Terminal').getAttribute('data-color')).toBe('#666');
    expect(container.querySelector('[data-opacity]:not([data-opacity=""])')).toBeNull();
  });
});

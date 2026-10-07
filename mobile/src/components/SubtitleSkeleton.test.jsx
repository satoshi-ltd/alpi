import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

import { lineHeights } from '../theme/tokens';

vi.mock('react-native', () => ({
  View: ({ children, style, accessibilityElementsHidden, importantForAccessibility, ...p }) =>
    React.createElement('div', { ...p, 'data-height': style.height, 'data-hidden-ios': String(!!accessibilityElementsHidden), 'data-android': importantForAccessibility }, children),
}));
vi.mock('./SkeletonBar', () => ({ SkeletonBar: ({ width, height }) => React.createElement('i', { 'data-bar': `${width}x${height}` }) }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ fontSizes: { xs: 11 } }) }));

const { SubtitleSkeleton } = await import('./SubtitleSkeleton');

afterEach(cleanup);

describe('SubtitleSkeleton', () => {
  it('holds the subtitle line height with a bar the size of its text, and no word', () => {
    const { container } = render(<SubtitleSkeleton />);
    expect(Number(container.firstChild.dataset.height)).toBeCloseTo(11 * lineHeights.cozy);
    expect(container.querySelector('[data-bar]').dataset.bar).toBe('96x11');
    expect(container.textContent).toBe('');
  });

  it('stays silent to screen readers, since the page below already announces its own labelled wait', () => {
    const { container } = render(<SubtitleSkeleton />);
    expect(container.firstChild.dataset.hiddenIos).toBe('true');
    expect(container.firstChild.dataset.android).toBe('no-hide-descendants');
  });
});

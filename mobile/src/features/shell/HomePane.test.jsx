import React from 'react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => ({
  View: ({ children, style, ...p }) => React.createElement('div', p, children),
}));

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { bg: '#fff', line2: 'rgba(11,17,23,0.14)', accent: '#c90' } }),
}));

vi.mock('../../components/AlpiMark', () => ({
  AlpiMark: ({ color, size }) => React.createElement('span', { 'data-mark': color, 'data-size': size }),
}));

import { HomePane } from './HomePane';

describe('HomePane', () => {
  it('holds the detail pane with a silent mark — nothing to resume says nothing', () => {
    const { container } = render(<HomePane />);
    expect(container.querySelectorAll('[data-mark]')).toHaveLength(1);
    expect(container.textContent).toBe('');
  });

  it('tints the mark with the hairline token so it reads as a watermark, not an action', () => {
    const { container } = render(<HomePane />);
    expect(container.querySelector('[data-mark]').getAttribute('data-mark')).toBe(
      'rgba(11,17,23,0.14)',
    );
  });
});

describe('HomePane is a state, not a launcher', () => {
  const source = readFileSync(join(import.meta.dirname, 'HomePane.jsx'), 'utf8');

  it.each(['Composer', 'useChatSend', 'useProfileSummaries', 'useRouter'])(
    'never reaches for %s again — arrival resumes the newest subject instead',
    (symbol) => {
      expect(source).not.toMatch(new RegExp(symbol));
    },
  );
});

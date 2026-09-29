import React from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

import { PaneContext } from './PaneContext';
import { SettingsSurface, useWideSettings } from './SettingsSurface';

afterEach(cleanup);

function Probe() {
  const wide = useWideSettings();
  return React.createElement('span', { 'data-testid': 'probe' }, wide ? 'wide' : 'compact');
}

function pane(twoPane) {
  return { twoPane, side: twoPane ? 'detail' : 'full', sidebarOpen: true, toggleSidebar() {} };
}

describe('useWideSettings', () => {
  it('is wide only inside a settings surface on two panes', () => {
    render(
      React.createElement(PaneContext.Provider, { value: pane(true) },
        React.createElement(SettingsSurface, null, React.createElement(Probe)),
      ),
    );
    expect(screen.getByTestId('probe').textContent).toBe('wide');
  });

  it('stays compact on two panes outside a settings surface', () => {
    render(React.createElement(PaneContext.Provider, { value: pane(true) }, React.createElement(Probe)));
    expect(screen.getByTestId('probe').textContent).toBe('compact');
  });

  it('survives a fold: the pane flips without changing the hook count', () => {
    const tree = (twoPane) =>
      React.createElement(PaneContext.Provider, { value: pane(twoPane) },
        React.createElement(SettingsSurface, null, React.createElement(Probe)),
      );
    const { rerender } = render(tree(true));
    expect(screen.getByTestId('probe').textContent).toBe('wide');
    expect(() => rerender(tree(false))).not.toThrow();
    expect(screen.getByTestId('probe').textContent).toBe('compact');
    expect(() => rerender(tree(true))).not.toThrow();
    expect(screen.getByTestId('probe').textContent).toBe('wide');
  });
});

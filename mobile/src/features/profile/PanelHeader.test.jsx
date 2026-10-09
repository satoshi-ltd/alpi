import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

vi.mock('../../components/Fold', () => ({ Fold: () => null }));
vi.mock('../../components/ScreenHeader', () => ({ ScreenHeader: ({ title, subtitle }) => React.createElement('header', {}, `${title}|${subtitle}`) }));
vi.mock('../../hooks/useSubject', () => ({ useProfile: () => ({ profile: { accent: '#123456', fold: 'diamond' } }) }));

import { PanelHeader } from './PanelHeader';

afterEach(cleanup);

describe('panel header', () => {
  it('names the default profile alpi, like the chat and the settings do', () => {
    render(<PanelHeader profile="default" section="SCHEDULES" count={4} />);
    expect(screen.getByText('alpi|SCHEDULES · 4')).toBeTruthy();
  });

  it('keeps any other profile name as it is', () => {
    render(<PanelHeader profile="scout" section="TOOLS" />);
    expect(screen.getByText('scout|TOOLS')).toBeTruthy();
  });
});

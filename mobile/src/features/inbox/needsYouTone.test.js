import { describe, expect, it } from 'vitest';

import { palettes } from '../../theme/tokens';
import { activitySections, activityTint } from '../shell/ActivityList';
import { stateColor } from './RowState';

const norm = (hex) => String(hex).toLowerCase();

describe.each(['light', 'dark'])('needs you vs working in %s', (mode) => {
  const colors = palettes[mode];

  it('keeps the warning text off the amber accent', () => {
    expect(norm(colors.warningText)).not.toBe(norm(colors.accent));
  });

  it('paints the inbox row state apart', () => {
    expect(stateColor('needs-you', colors)).toBe(colors.warningText);
    expect(stateColor('working', colors)).toBe(colors.accent);
    expect(norm(stateColor('needs-you', colors))).not.toBe(norm(stateColor('working', colors)));
  });

  it('paints the activity rows apart', () => {
    const [needs, running] = activitySections({
      needsYou: [{ request_id: 'r1', kind: 'approval', profile: 'doc', ts: 0 }],
      running: [{ profile: 'doc', session_id: 's1' }],
      scheduled: [],
    }, 0);
    const needsTint = activityTint(needs.rows[0].tone, colors);
    const workingTint = activityTint(running.rows[0].tone, colors);
    expect(needsTint).toBe(colors.warningText);
    expect(workingTint).toBe(colors.accent);
    expect(norm(needsTint)).not.toBe(norm(workingTint));
  });
});

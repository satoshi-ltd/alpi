import { describe, expect, it } from 'vitest';

import { isDefaultProfile, splitDefaultProfile, withoutDefaultPin } from '../../../common/rosterOrder.mjs';

describe('rosterOrder on the phone', () => {
  it('splits the default profile out of the summaries the daemon sends', () => {
    const list = [{ name: 'doc' }, { name: 'default', is_default: true }];
    expect(splitDefaultProfile(list)).toEqual({ front: list[1], rest: [list[0]] });
  });

  it('finds no front on a scoped connection', () => {
    expect(splitDefaultProfile([{ name: 'sentinel' }]).front).toBeNull();
  });

  it('agrees with the desktop on what the default is and which pins it ignores', () => {
    expect(isDefaultProfile({ name: 'default' })).toBe(true);
    expect(isDefaultProfile({ name: 'alpi' })).toBe(false);
    expect(withoutDefaultPin(['default', 'doc'])).toEqual(['doc']);
  });
});

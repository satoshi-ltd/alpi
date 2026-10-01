import { describe, expect, it } from 'vitest';

import { EMPTY, postsHint } from '../../../common/emptyCopy.mjs';
import { emptyCopyProblems } from '../../../common/emptyCopy.rules.mjs';

describe('shared empty-state copy on mobile', () => {
  it('speaks in the shared voice', () => {
    expect(emptyCopyProblems(EMPTY)).toEqual([]);
  });

  it('names the hub in the thread hint', () => {
    expect(postsHint('scout')).toBe('Direct @scout to open a #task.');
  });
});

import { describe, expect, it } from 'vitest';
import { PLAIN_ERROR_CASES, PLAIN_ERROR_UNTOUCHED } from '../../../common/plainError.fixtures.mjs';
import { plainError } from '../../../common/plainError.mjs';

describe('plain words for the app\'s own errors', () => {
  it.each(PLAIN_ERROR_CASES)('turns %j into a sentence', (raw, sentence) => {
    expect(plainError(raw)).toBe(sentence);
  });

  it.each(PLAIN_ERROR_UNTOUCHED)('leaves %j as it is', (raw) => {
    expect(plainError(raw)).toBe(raw);
  });
});

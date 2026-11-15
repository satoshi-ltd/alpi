import { useState } from 'react';
import { focusRing } from '../../../common/tokens.mjs';
import { ringColor } from './well';

export function useFocusRing() {
  const [focused, setFocused] = useState(false);
  return [focused, { onFocus: () => setFocused(true), onBlur: () => setFocused(false) }];
}

export function focusRingStyle(colors, focused) {
  if (!focused) return null;
  return { outlineStyle: 'solid', outlineWidth: focusRing.width, outlineOffset: focusRing.offset, outlineColor: ringColor(colors) };
}

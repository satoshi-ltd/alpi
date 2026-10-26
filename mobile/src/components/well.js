import { useState } from 'react';
import { mixHex } from '../../../common/color.mjs';
import { radii } from '../theme/tokens';

export function wellStyle(colors, { focused = false, error = false } = {}) {
  return {
    backgroundColor: focused ? mixHex(colors.field, 0.9, colors.ink) : colors.field,
    borderRadius: radii.xs,
    borderWidth: 2,
    borderColor: error ? colors.dangerText : focused ? colors.focus : 'transparent',
  };
}

export function useWell(colors, error = false) {
  const [focused, setFocused] = useState(false);
  return [wellStyle(colors, { focused, error }), { onFocus: () => setFocused(true), onBlur: () => setFocused(false) }];
}

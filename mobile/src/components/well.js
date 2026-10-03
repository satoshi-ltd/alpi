import { useState } from 'react';
import { mixHex } from '../../../common/color.mjs';
import { radii } from '../theme/tokens';

export function wellStyle(colors, { focused = false, error = false } = {}) {
  return {
    backgroundColor: focused ? mixHex(colors.bgInput, 0.9, colors.ink) : colors.bgInput,
    borderRadius: radii.xs,
    borderWidth: 1,
    borderColor: error ? colors.dangerText : focused ? `${colors.ink}4d` : 'transparent',
  };
}

export function useWell(colors, error = false) {
  const [focused, setFocused] = useState(false);
  return [wellStyle(colors, { focused, error }), { onFocus: () => setFocused(true), onBlur: () => setFocused(false) }];
}

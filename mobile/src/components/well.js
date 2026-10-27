import { useState } from 'react';
import { radii } from '../theme/tokens';

export function wellStyle(colors, { focused = false, error = false, disabled = false } = {}) {
  return {
    backgroundColor: disabled ? colors.field : colors.bgElev,
    borderRadius: radii.xs,
    borderWidth: 1,
    borderColor: disabled ? 'transparent' : error ? colors.dangerText : focused ? colors.edge : colors.line2,
  };
}

export function useWell(colors, error = false, disabled = false) {
  const [focused, setFocused] = useState(false);
  return [wellStyle(colors, { focused, error, disabled }), { onFocus: () => setFocused(true), onBlur: () => setFocused(false) }];
}

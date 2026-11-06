import { useState } from 'react';
import { wellStates } from '../../../common/well.mjs';
import { alpha, radii } from '../theme/tokens';

export function wellStyle(colors, { focused = false, error = false, disabled = false } = {}) {
  const off = wellStates.disabled;
  const edge = disabled ? off.edge : error ? colors[wellStates.error.ring] : focused ? colors[wellStates.edge.focus] : colors[wellStates.edge.rest];
  return {
    backgroundColor: disabled ? colors[off.surface] : colors.bgElev,
    borderRadius: radii.xs,
    borderWidth: wellStates.edge.width,
    borderColor: edge,
    ...(disabled ? { opacity: alpha[off.fade] } : {}),
  };
}

export function useWell(colors, error = false, disabled = false) {
  const [focused, setFocused] = useState(false);
  return [wellStyle(colors, { focused, error, disabled }), { onFocus: () => setFocused(true), onBlur: () => setFocused(false) }];
}

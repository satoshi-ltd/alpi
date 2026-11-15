import { useState } from 'react';
import { wellStates } from '../../../common/well.mjs';
import { fieldFocus, focusRing } from '../../../common/tokens.mjs';
import { alpha, radii } from '../theme/tokens';

export const ringColor = (colors) => `${colors.ink}${Math.round(focusRing.alpha * 255).toString(16).padStart(2, '0')}`;

export const recess = (colors) => (colors.bgElev === colors.bgPane ? colors.field : colors.bgPane);

export function wellStyle(colors, { focused = false, error = false, disabled = false, float = false } = {}) {
  const off = wellStates.disabled;
  const edge = disabled ? 'transparent' : error ? colors[wellStates.error.ring] : focused ? colors[fieldFocus.ink] : 'transparent';
  return {
    backgroundColor: disabled ? colors[off.surface] : float ? recess(colors) : colors.fill,
    borderRadius: radii[wellStates.radius],
    borderWidth: fieldFocus.width,
    borderColor: edge,
    ...(disabled ? { opacity: alpha[off.fade] } : {}),
  };
}

export function useWell(colors, error = false, disabled = false, float = false) {
  const [focused, setFocused] = useState(false);
  return [wellStyle(colors, { focused, error, disabled, float }), { onFocus: () => setFocused(true), onBlur: () => setFocused(false) }];
}

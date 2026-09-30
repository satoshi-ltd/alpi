import { useEffect, useState } from 'react';
import { Switch } from 'react-native';

import { selection } from '../lib/haptics';
import { useTheme } from '../theme/ThemeContext';

// The thumb follows the finger at once; onChange returning false, or rejecting, snaps it back.
export function Toggle({ on, onChange, disabled = false, label, color }) {
  const { colors } = useTheme();
  const [shown, setShown] = useState(!!on);
  useEffect(() => {
    setShown(!!on);
  }, [on]);
  const flip = (next) => {
    setShown(next);
    selection();
    const revert = () => setShown(!next);
    let result;
    try {
      result = onChange?.(next);
    } catch {
      revert();
      return;
    }
    if (result === false) revert();
    else if (result && typeof result.then === 'function') result.then((ok) => { if (ok === false) revert(); }, revert);
  };
  return (
    <Switch
      value={shown}
      onValueChange={disabled ? undefined : flip}
      disabled={disabled}
      accessibilityLabel={label}
      trackColor={{ false: colors.line2, true: color ?? colors.accent }}
      thumbColor={colors.bgPane}
      ios_backgroundColor={colors.line2}
    />
  );
}

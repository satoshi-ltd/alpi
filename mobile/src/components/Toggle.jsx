import { useEffect, useState } from 'react';
import { Switch } from 'react-native';

import { tapFeedback } from '../lib/haptics';
import { useTheme } from '../theme/ThemeContext';

// The thumb follows the finger at once; the prop catches up when the daemon round-trip lands.
export function Toggle({ on, onChange, disabled = false, label, color }) {
  const { colors } = useTheme();
  const [shown, setShown] = useState(!!on);
  useEffect(() => {
    setShown(!!on);
  }, [on]);
  const flip = (next) => {
    setShown(next);
    tapFeedback();
    onChange?.(next);
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

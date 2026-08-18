import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { alpha, glyphSize, glyphSizeMd, pulseDuration } from '../theme/tokens';
import { Diamond } from './Diamond';

export function DiamondStack({ color, size, pulse = false }) {
  const dot = size === 'md' ? glyphSizeMd : glyphSize;
  const box = dot * 1.5;
  const top = (box - dot) / 2;
  const [backPulse, setBackPulse] = useState(false);

  useEffect(() => {
    if (!pulse) {
      setBackPulse(false);
      return;
    }
    const timer = setTimeout(() => setBackPulse(true), pulseDuration / 4);
    return () => clearTimeout(timer);
  }, [pulse]);

  return (
    <View style={{ width: box, height: box, flexShrink: 0, overflow: 'visible' }}>
      <View style={{ position: 'absolute', top, left: dot / 2, opacity: alpha.faint }}>
        <Diamond color={color} size={size} pulse={backPulse} />
      </View>
      <View style={{ position: 'absolute', top, left: 0 }}>
        <Diamond color={color} size={size} pulse={pulse} />
      </View>
    </View>
  );
}

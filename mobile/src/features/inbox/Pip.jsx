import { View } from 'react-native';
import { radii } from '../../theme/tokens';

import { ThinkingDots } from '../chat/ThinkingDots';

export function Pip({ kind, color, bg }) {
  if (kind !== 'working') return null;
  return (
    <View
      style={{
        position: 'absolute',
        bottom: -1,
        right: -1,
        width: 16,
        height: 16,
        borderRadius: radii.sm,
        backgroundColor: bg,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <ThinkingDots color={color} />
    </View>
  );
}

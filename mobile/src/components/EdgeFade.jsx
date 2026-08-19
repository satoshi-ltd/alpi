import { View } from 'react-native';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';

const AXIS = {
  left: { x1: '0', y1: '0', x2: '1', y2: '0' },
  right: { x1: '1', y1: '0', x2: '0', y2: '0' },
  top: { x1: '0', y1: '0', x2: '0', y2: '1' },
  bottom: { x1: '0', y1: '1', x2: '0', y2: '0' },
};

const BOX = {
  left: { left: 0, top: 0, bottom: 0 },
  right: { right: 0, top: 0, bottom: 0 },
  top: { top: 0, left: 0, right: 0 },
  bottom: { bottom: 0, left: 0, right: 0 },
};

const RAMP = [[0, 1], [0.28, 0.86], [0.58, 0.46], [0.82, 0.14], [1, 0]];

export function EdgeFade({ side, color, size = 28 }) {
  const id = `edge-fade-${side}`;
  const span = side === 'left' || side === 'right' ? { width: size } : { height: size };
  return (
    <View
      pointerEvents="none"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      testID={`edge-fade-${side}`}
      style={[{ position: 'absolute' }, BOX[side], span]}
    >
      <Svg width="100%" height="100%">
        <Defs>
          <LinearGradient id={id} {...AXIS[side]}>
            {RAMP.map(([offset, opacity]) => (
              <Stop key={offset} offset={String(offset)} stopColor={color} stopOpacity={String(opacity)} />
            ))}
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill={`url(#${id})`} />
      </Svg>
    </View>
  );
}

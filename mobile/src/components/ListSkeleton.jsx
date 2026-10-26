import { View } from 'react-native';

import { RowGroup, RowSeparator } from './Row';
import { SkeletonBar, STAGGER_MS } from './SkeletonBar';
import { useTheme } from '../theme/ThemeContext';
import { lineHeights, mobile, radii, space } from '../theme/tokens';

const SHAPES = [[120, 200], [90, 230], [140, 170], [100, 210], [130, 180]];

function Line({ size, width, delay }) {
  return (
    <View data-line={size} style={{ height: size * lineHeights.cozy, justifyContent: 'center' }}>
      <SkeletonBar width={width} height={size} delay={delay} />
    </View>
  );
}

export function ListSkeleton({ rows = 3, label, flat = false, title = 'lg', helper = 'xs', value = false, style }) {
  const { fontSizes } = useTheme();
  const Card = flat ? View : RowGroup;
  return (
    <View accessible accessibilityRole="progressbar" accessibilityLabel={label} data-skeleton="list" style={style}>
      <Card>
        {Array.from({ length: rows }, (_, i) => {
          const [titleW, helperW] = SHAPES[i % SHAPES.length];
          return (
            <View key={i}>
              {i > 0 ? <RowSeparator /> : null}
              <View data-row="" style={{ minHeight: mobile.tap, flexDirection: 'row', alignItems: 'center', gap: space.s5, paddingHorizontal: space.s7, paddingVertical: space.s6 }}>
                <View style={{ flex: 1, gap: space.s1 }}>
                  <Line size={fontSizes[title]} width={titleW} delay={i * STAGGER_MS} />
                  {helper ? <Line size={fontSizes[helper]} width={helperW} delay={i * STAGGER_MS + STAGGER_MS / 2} /> : null}
                </View>
                {value ? <SkeletonBar width={56} height={fontSizes.md} radius={radii.tag} delay={i * STAGGER_MS} /> : null}
              </View>
            </View>
          );
        })}
      </Card>
    </View>
  );
}

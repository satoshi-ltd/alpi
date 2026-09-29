import { Children, Fragment } from 'react';
import { View } from 'react-native';

import { useTheme } from '../theme/ThemeContext';
import { space } from '../theme/tokens';

const SEP_W = 1;
const SEP_H = 10;

export function metaItems(children) {
  const inner = children?.type === Fragment ? children.props.children : children;
  return Children.toArray(inner).filter((c) => c !== null && c !== false);
}

export function MetaStrip({ children, style }) {
  const { colors } = useTheme();
  const list = metaItems(children);
  return (
    <View style={[{ flexDirection: 'row', alignItems: 'center', gap: space.s6 }, style]}>
      {list.map((child, i) => (
        <Fragment key={child.key ?? i}>
          {i > 0 ? <View testID="meta-sep" style={{ width: SEP_W, height: SEP_H, backgroundColor: colors.line2 }} /> : null}
          {child}
        </Fragment>
      ))}
    </View>
  );
}

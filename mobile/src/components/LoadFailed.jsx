import { Text, View } from 'react-native';

import { plainError } from '../../../common/plainError.mjs';
import { lineHeights, space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';
import { Button } from './Button';
import { EmptyState } from './EmptyState';

export function LoadFailed({ label, error, onRetry, inline = false, showDetail = false }) {
  const { colors, fonts, fontSizes } = useTheme();
  const message = `Couldn't load ${label}`;
  const detail = error ? plainError(error?.message ?? error) : null;
  if (inline) {
    return (
      <View accessibilityRole="alert" style={{ flexDirection: 'row', alignItems: 'center', gap: space.s4, paddingHorizontal: space.s7, paddingVertical: space.s6 }}>
        <View style={{ flex: 1, gap: space.s1 }}>
          <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.dangerText }}>{message}</Text>
          {showDetail && detail ? (
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * lineHeights.cozy, color: colors.ink3 }}>{detail}</Text>
          ) : null}
        </View>
        {onRetry ? <Button title="Retry" variant="secondary" size="sm" onPress={onRetry} /> : null}
      </View>
    );
  }
  return <EmptyState alert title={message} detail={detail} action={onRetry ? { label: 'Retry', onPress: onRetry } : null} />;
}

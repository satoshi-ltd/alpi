import { Pressable, Text, View } from 'react-native';
import { mobile, space } from '../../theme/tokens';

import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';

function FailureRow({ children, onRetry }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ paddingHorizontal: space.s7, flexDirection: 'row', alignItems: 'center', gap: space.s3, minHeight: mobile.tap }}>
      <Icon name="triangle-alert" size="xs" color={colors.danger} />
      <Text style={{ flex: 1, fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.dangerText }}>{children}</Text>
      {onRetry ? (
        <Pressable
          onPress={onRetry}
          accessibilityRole="button"
          accessibilityLabel="Retry"
          style={{ minHeight: mobile.tap, minWidth: mobile.tap, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.s3 }}
        >
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.sm, color: colors.dangerText }}>Retry</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export function FailedSend({ onRetry }) {
  return <FailureRow onRetry={onRetry}>Message failed to send.</FailureRow>;
}

export function TimeoutBanner({ profileId, onRetry }) {
  return <FailureRow onRetry={onRetry}>{`@${profileId} didn't respond in 60s.`}</FailureRow>;
}

export function FailedVoice({ duration, onRetry }) {
  return <FailureRow onRetry={onRetry}>{`Voice message (${duration}s) failed to upload.`}</FailureRow>;
}

export function FailedToolCall({ name, reason }) {
  return <FailureRow>{`${name} · ${reason}`}</FailureRow>;
}

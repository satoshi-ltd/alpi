import { Pressable, Text, View } from 'react-native';
import { radii, space } from '../../theme/tokens';

import { Banner } from '../../components/Banner';
import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';

export function FailedSend({ onRetry }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ paddingHorizontal: space.s7, flexDirection: 'row', justifyContent: 'flex-end' }}>
      <Pressable onPress={onRetry} hitSlop={6} style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
        <Icon name="refresh" size="xs" color={colors.danger} />
        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.danger }}>
          failed to send · Retry
        </Text>
      </Pressable>
    </View>
  );
}

export function TimeoutBanner({ profileId, onRetry }) {
  return (
    <View style={{ marginHorizontal: space.s7 }}>
      <Banner kind="warning" action="Retry" onAction={onRetry}>
        @{profileId} didn't respond in 60s. Daemon is healthy.
      </Banner>
    </View>
  );
}

export function FailedVoice({ duration, onRetry }) {
  const { colors, fonts, fontSizes, mobile } = useTheme();
  return (
    <View style={{ alignItems: 'flex-end', paddingHorizontal: space.s7 }}>
      <View
        style={{
          maxWidth: `${mobile.bubbleMaxPct * 100}%`,
          flexDirection: 'row',
          alignItems: 'center',
          gap: space.s4,
          paddingHorizontal: space.s6,
          paddingVertical: space.s4,
          borderRadius: radii.bubble,
          borderTopRightRadius: radii.md,
          backgroundColor: `${colors.danger}1c`,
        }}
      >
        <Icon name="mic" size="sm" color={colors.danger} />
        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.danger }}>
          {duration}s · voice upload failed
        </Text>
        <Pressable onPress={onRetry} hitSlop={6}>
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.sm, color: colors.danger }}>
            Retry
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

export function FailedToolCall({ name, reason }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ paddingHorizontal: space.s7, flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.danger }}>×</Text>
      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.danger }}>
        {name} · {reason}
      </Text>
    </View>
  );
}

import { StyleSheet, Text, View } from 'react-native';

import { Sheet } from '../../components/Sheet';
import { useTheme } from '../../theme/ThemeContext';
import { space } from '../../theme/tokens';

const STYLES = StyleSheet.create({
  body: {
    paddingHorizontal: space.s7,
    paddingTop: space.s3,
    paddingBottom: space.s5,
    gap: space.s5,
  },
});

export function NotificationPrimer({ open, onEnable, onDecline }) {
  const { colors, fonts, fontSizes } = useTheme();

  return (
    <Sheet
      open={open}
      onClose={onDecline}
      title="Stay in the loop"
      subtitle="notifications · straight from your daemon"
      dismissible={false}
      primaryAction={[
        { id: 'later', label: 'Not now', variant: 'ghost', onPress: onDecline },
        { id: 'enable', label: 'Enable notifications', onPress: onEnable },
      ]}
    >
      <View style={STYLES.body}>
        <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink2 }}>
          alpi tells you when an agent needs an approval, finishes a task, or hits a budget
          threshold.
        </Text>
        <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink2 }}>
          Alerts are built on this phone from your own daemon&apos;s events. Nothing is routed
          through Apple, Google, or any push service.
        </Text>
        <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>
          Delivery starts when you enable it — you can also turn it on later in
          Settings → Notifications.
        </Text>
      </View>
    </Sheet>
  );
}

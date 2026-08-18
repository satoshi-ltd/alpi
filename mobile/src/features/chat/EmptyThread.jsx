import { StyleSheet, Text, View } from 'react-native';

import { AlpiMark } from '../../components/AlpiMark';
import { CONTENT_MAX_W } from '../../lib/panes';
import { lineHeights, space, tracking } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeContext';

const STYLES = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.s10 },
  column: { alignSelf: 'center', width: '100%', maxWidth: CONTENT_MAX_W, alignItems: 'center', gap: space.s7 },
  heading: { textAlign: 'center' },
  detail: { textAlign: 'center' },
});

export function EmptyThread({ heading, detail, accent }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={STYLES.root}>
      <View style={STYLES.column}>
        <AlpiMark color={accent ?? colors.ink3} />
        <Text
          style={[
            STYLES.heading,
            {
              fontFamily: fonts.sans.semibold,
              fontSize: fontSizes['2xl'],
              lineHeight: fontSizes['2xl'] * lineHeights.cozy,
              letterSpacing: fontSizes['2xl'] * tracking.tight,
              color: colors.ink,
            },
          ]}
        >
          {heading}
        </Text>
        {detail ? (
          <Text
            style={[
              STYLES.detail,
              {
                fontFamily: fonts.mono,
                fontSize: fontSizes.xs,
                lineHeight: fontSizes.xs * lineHeights.cozy,
                color: colors.ink3,
              },
            ]}
          >
            {detail}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

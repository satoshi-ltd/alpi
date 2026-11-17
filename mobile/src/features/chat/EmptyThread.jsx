import { Pressable, ScrollView, Text } from 'react-native';

import { MARK_SIZES } from '../../../../common/agentMarks.mjs';
import { CONTINUE_LABEL, introAge } from '../../../../common/threadIntro.mjs';
import { EmptyState } from '../../components/EmptyState';
import { Fold } from '../../components/Fold';
import { focusRingStyle, useFocusRing } from '../../components/focusRing';
import { Icon } from '../../components/Icon';
import { CONTENT_MAX_W } from '../../lib/panes';
import { buttonRadius } from '../../../../common/button.mjs';
import { lineHeights, radii, space } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeContext';

const BIO_LINES = 5;
const TOUCH = 44;

function Continue({ session, onPress }) {
  const { colors, fonts, fontSizes } = useTheme();
  const age = introAge(session.ts);
  const [focused, focusHandlers] = useFocusRing();
  return (
    <Pressable
      testID="thread-continue"
      accessibilityRole="button"
      accessibilityLabel={`${CONTINUE_LABEL} “${session.title}”${age ? `, ${age}` : ''}`}
      onPress={() => onPress(session.id)}
      {...focusHandlers}
      style={({ pressed }) => ({
        ...focusRingStyle(colors, focused),
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s2,
        minHeight: TOUCH,
        maxWidth: '100%',
        marginTop: space.s3,
        paddingHorizontal: space.s4,
        borderRadius: radii[buttonRadius],
        backgroundColor: pressed ? colors.pressed : colors.fill,
      })}
    >
      <Icon name="history" size="xs" color={colors.ink2} />
      <Text numberOfLines={1} style={{ flexShrink: 1, fontFamily: fonts.sans.medium, fontSize: fontSizes.sm, color: colors.ink }}>
        {CONTINUE_LABEL} “{session.title}”
      </Text>
      {age ? <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, color: colors.ink3 }}>{age}</Text> : null}
    </Pressable>
  );
}

export function EmptyThread({ heading, detail, accent, shape, state, bio, session, onContinue }) {
  const { colors, fonts, fontSizes } = useTheme();
  const intro = bio ? (
    <Text
      testID="thread-bio"
      numberOfLines={BIO_LINES}
      style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, lineHeight: fontSizes.md * lineHeights.cozy, color: colors.ink2, textAlign: 'center' }}
    >
      {bio}
    </Text>
  ) : null;
  return (
    <ScrollView testID="thread-intro" contentContainerStyle={{ flexGrow: 1 }} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
    <EmptyState
      hero
      monoDetail
      maxWidth={CONTENT_MAX_W}
      mark={<Fold shape={shape} color={accent ?? colors.ink3} size={MARK_SIZES.hero} state={state} />}
      title={heading}
      lead={intro}
      detail={detail}
      footer={session && onContinue ? <Continue session={session} onPress={onContinue} /> : null}
    />
    </ScrollView>
  );
}

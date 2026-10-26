import { Pressable, ScrollView, Text, View } from 'react-native';
import { mobile, radii, space } from '../../theme/tokens';

import { FALLBACK_ACCENT } from '../../../../common/folds.mjs';
import { Fold } from '../../components/Fold';
import { Pill } from '../../components/Pill';
import { useProfileSummaries } from '../../hooks/useDaemonData';
import { PANE_PAD_X } from '../../lib/panes';
import { modelLabel } from '../../lib/modelLabel';
import { profileLabel } from '../../lib/profileName';
import { useTheme } from '../../theme/ThemeContext';

const VISIBLE_ROWS = 4;

export function MentionPopover({ candidates = [], token = '', onPick }) {
  const { colors, fonts, fontSizes, shadow } = useTheme();
  const summaries = useProfileSummaries();
  const profiles = summaries.data?.profiles ?? [];
  const empty = !candidates.length;
  if (empty && !token) return null;
  return (
    <View
      style={{
        marginHorizontal: PANE_PAD_X,
        marginBottom: space.s3,
        backgroundColor: colors.bgElev,
        borderRadius: radii.xs,
        overflow: 'hidden',
        ...shadow.float,
      }}
    >
      {empty ? (
        <View style={{ minHeight: mobile.tap, paddingHorizontal: space.s7, justifyContent: 'center' }}>
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3 }}>
            {`No peer matches “${token}”`}
          </Text>
        </View>
      ) : (
        <ScrollView keyboardShouldPersistTaps="always" style={{ maxHeight: mobile.tap * VISIBLE_ROWS }}>
          {candidates.map((c, i) => {
            const isHub = c.role === 'hub';
            const profile = profiles.find((p) => p.name === c.id);
            const accent = profile?.accent ?? FALLBACK_ACCENT;
            return (
              <Pressable
                key={c.id}
                onPress={() => onPick?.(c)}
                accessibilityRole="button"
                accessibilityLabel={`Mention @${profileLabel(c.id)}`}
                android_ripple={{ color: colors.selected }}
                style={({ pressed }) => ({
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: space.s4,
                  minHeight: mobile.tap,
                  paddingHorizontal: space.s6,
                  backgroundColor: pressed ? colors.selected : 'transparent',
                  borderTopWidth: i === 0 ? 0 : 0.5,
                  borderTopColor: colors.line,
                })}
              >
                <Fold fold={profile?.fold} color={accent} />
                <Text style={{ flex: 1, fontFamily: fonts.mono, fontSize: fontSizes.md, color: colors.ink }}>
                  @{profileLabel(c.id)}
                </Text>
                {isHub ? <Pill tone="on">hub</Pill> : null}
                {profile?.model ? (
                  <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3 }}>
                    {modelLabel(profile.model)}
                  </Text>
                ) : null}
              </Pressable>
            );
          })}
        </ScrollView>
      )}
    </View>
  );
}

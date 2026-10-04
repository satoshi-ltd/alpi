import { Pressable, Text, View } from 'react-native';
import { radii, space } from '../../theme/tokens';

import { FALLBACK_ACCENT } from '../../../../common/folds.mjs';
import { Fold } from '../../components/Fold';
import { Pill } from '../../components/Pill';
import { useProfileSummaries } from '../../hooks/useDaemonData';
import { modelLabel } from '../../lib/modelLabel';
import { profileLabel } from '../../lib/profileName';
import { useTheme } from '../../theme/ThemeContext';

export function MentionPopover({ candidates = [], onPick }) {
  const { colors, fonts, fontSizes, shadow } = useTheme();
  const summaries = useProfileSummaries();
  const profiles = summaries.data?.profiles ?? [];
  if (!candidates.length) return null;
  return (
    <View
      style={{
        marginHorizontal: space.s5,
        marginBottom: space.s3,
        backgroundColor: colors.bgElev,
        borderRadius: radii.xs,
        overflow: 'hidden',
        ...shadow.base,
      }}
    >
      {candidates.map((c, i) => {
        const isHub = c.role === 'hub';
        const profile = profiles.find((p) => p.name === c.id);
        const accent = profile?.accent ?? FALLBACK_ACCENT;
        return (
          <Pressable
            key={c.id}
            onPress={() => onPick?.(c)}
            android_ripple={{ color: colors.selected }}
            style={({ pressed }) => ({
              flexDirection: 'row',
              alignItems: 'center',
              gap: space.s4,
              paddingHorizontal: space.s6,
              paddingVertical: space.s4,
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
    </View>
  );
}

import { Pressable, Text, View } from 'react-native';
import { radii, space , fontSizes} from '../../theme/tokens';

import { Diamond } from '../../components/Diamond';
import { Pill } from '../../components/Pill';
import { useProfileSummaries } from '../../hooks/useDaemonData';
import { accentForProfile } from '../../theme/accents';
import { profileLabel } from '../../lib/profileLabel';
import { useTheme } from '../../theme/ThemeContext';

export function MentionPopover({ candidates = [], onPick }) {
  const { colors, fonts, fontSizes } = useTheme();
  const summaries = useProfileSummaries();
  const profiles = summaries.data?.profiles ?? [];
  if (!candidates.length) return null;
  return (
    <View
      style={{
        marginHorizontal: space.s5,
        marginBottom: space.s3,
        backgroundColor: colors.bgElev,
        borderRadius: radii['2xl'],
        overflow: 'hidden',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 8 },
        shadowOpacity: 0.16,
        shadowRadius: 16,
        elevation: 6,
      }}
    >
      {candidates.map((c, i) => {
        const isHub = c.role === 'hub';
        const profile = profiles.find((p) => p.name === c.id);
        const accent = profile?.accent ?? accentForProfile(c.id);
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
            <Diamond color={accent} />
            <Text style={{ flex: 1, fontFamily: fonts.mono, fontSize: fontSizes.md, color: colors.ink }}>
              @{profileLabel(c.id)}
            </Text>
            {isHub ? <Pill tone="on">hub</Pill> : null}
            {profile?.model ? (
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>
                {profile.model.split('/').slice(1).join('/')}
              </Text>
            ) : null}
          </Pressable>
        );
      })}
    </View>
  );
}

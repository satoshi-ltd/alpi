import { Pressable, StyleSheet, Text, View } from 'react-native';
import { radii, space } from '../../theme/tokens';

import { Fold } from '../../components/Fold';
import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';

const STATE_WORD = { current: 'running', skipped: 'skipped', blocked: 'blocked' };

const STYLES = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s2,
    paddingHorizontal: space.s4,
    borderWidth: 0.5,
    borderRadius: radii.xs,
  },
});

export function phaseLabel(chip) {
  const word = STATE_WORD[chip.state] ?? chip.state;
  return [`#${chip.slug}`, chip.owner ? `@${chip.owner}` : null, chip.assignee ? `→ @${chip.assignee}` : null, word].filter(Boolean).join(' · ');
}

export function PhaseMark({ name, profileOf, pulse = false, size = 12 }) {
  if (!name) return null;
  const profile = profileOf?.(name);
  if (!profile) return <Fold fold="diamond" size={size} unfolded />;
  return <Fold fold={profile.fold} color={profile.accent} size={size} pulse={pulse} />;
}

export function PhaseChip({ chip, profileOf, height = 28, onPress, hint, testID }) {
  const { colors, fonts, fontSizes } = useTheme();
  const blocked = chip.state === 'blocked';
  const working = chip.state === 'current';
  const word = STATE_WORD[chip.state];
  const Wrapper = onPress ? Pressable : View;
  return (
    <Wrapper
      testID={testID ?? `phase-${chip.slug}`}
      accessible
      accessibilityRole={onPress ? 'button' : undefined}
      accessibilityLabel={phaseLabel(chip)}
      accessibilityHint={hint}
      onPress={onPress}
      style={[STYLES.chip, { minHeight: height, borderColor: blocked ? colors.danger : 'transparent', backgroundColor: working || blocked ? colors.selected : colors.hover }]}
    >
      <PhaseMark name={chip.owner} profileOf={profileOf} pulse={working && !chip.assignee} />
      <Text
        style={{
          fontFamily: working || blocked ? fonts.monoSemibold : fonts.mono,
          fontSize: fontSizes.sm,
          color: chip.state === 'pending' ? colors.ink2 : chip.state === 'skipped' ? colors.ink3 : colors.ink,
          textDecorationLine: chip.state === 'skipped' ? 'line-through' : 'none',
        }}
      >
        #{chip.slug}
      </Text>
      {chip.assignee ? (
        <>
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>→</Text>
          <PhaseMark name={chip.assignee} profileOf={profileOf} pulse={working} />
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink }}>@{chip.assignee}</Text>
        </>
      ) : null}
      {chip.state === 'completed' ? <Icon name="check" size="sm" color={colors.ink} /> : null}
      {word ? (
        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: blocked ? colors.dangerText : colors.ink3 }}>{word}</Text>
      ) : null}
    </Wrapper>
  );
}

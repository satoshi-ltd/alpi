import { Pressable, ScrollView, Text, View } from 'react-native';

import { Sheet } from '../../components/Sheet';
import { fontSizes, radii, space } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeContext';
import { useApprovalQueue } from './useApprovalQueue';

const CHOICES = [
  { value: 'once', label: 'Allow once', hint: 'Approve just this command.' },
  { value: 'session', label: 'Allow this session', hint: 'Re-approve when the daemon restarts.' },
  { value: 'always', label: 'Always allow this pattern', hint: 'Persist in config.yaml.' },
  { value: 'deny', label: 'Deny', hint: 'Refuse — model will move on.', danger: true },
];

// Bridges the host-plane approval contract to a native sheet.
// Queue lives in useApprovalQueue (testable in jsdom); this file is rendering only.
export function ApprovalSheet() {
  const { colors, fonts } = useTheme();
  const { current, busy, error, respond } = useApprovalQueue();

  return (
    <Sheet
      open={!!current}
      onClose={() => respond('deny')}
      title={current ? `${(current.severity || 'caution').toUpperCase()} · ${current.pattern}` : ''}
      subtitle={current?.profile ? `profile: ${current.profile}` : null}
      maxHeight="78%"
    >
      {current ? (
        <View style={{ paddingHorizontal: space.s7, paddingBottom: space.s7, gap: space.s5 }}>
          <ScrollView
            style={{
              maxHeight: 160,
              backgroundColor: colors.bgInput,
              borderRadius: radii.md,
              borderWidth: 0.5,
              borderColor: colors.line,
              padding: space.s5,
            }}
          >
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink }}>
              {current.command}
            </Text>
          </ScrollView>

          <View style={{ gap: space.s2 }}>
            {CHOICES.map((c) => (
              <Pressable
                key={c.value}
                disabled={busy}
                onPress={() => respond(c.value)}
                style={({ pressed }) => ({
                  paddingVertical: space.s5,
                  paddingHorizontal: space.s6,
                  borderRadius: radii.md,
                  borderWidth: 0.5,
                  borderColor: colors.line,
                  backgroundColor: pressed ? colors.hover : colors.bgPane,
                  opacity: busy ? 0.5 : 1,
                })}
              >
                <Text
                  style={{
                    fontFamily: fonts.sansMedium,
                    fontSize: fontSizes.sm,
                    color: c.danger ? colors.danger : colors.ink,
                  }}
                >
                  {c.label}
                </Text>
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
                  {c.hint}
                </Text>
              </Pressable>
            ))}
          </View>

          {error ? (
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.danger }}>
              {error}
            </Text>
          ) : null}
        </View>
      ) : null}
    </Sheet>
  );
}

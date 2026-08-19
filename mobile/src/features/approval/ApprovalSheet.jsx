import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { Diamond } from '../../components/Diamond';
import { Sheet } from '../../components/Sheet';
import { lineHeights, radii, space } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeContext';
import { useApprovalQueue } from './useApprovalQueue';

const ALLOW_CHOICES = [
  { value: 'once',    label: 'Allow once',        hint: 'just this invocation' },
  { value: 'session', label: 'Allow this session', hint: 'remember until daemon restarts' },
  { value: 'always',  label: 'Always allow',       hint: 'add to allowlist' },
];

export function ApprovalSheet() {
  const { colors, fonts, fontSizes } = useTheme();
  const { current, busy, error, respond } = useApprovalQueue();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!current?.deadline) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [current?.deadline]);

  const remaining = current?.deadline
    ? Math.max(0, Math.round((current.deadline - now) / 1000))
    : null;

  const severity = (current?.severity || 'caution').toLowerCase();
  const severityColor = severity === 'dangerous'
    ? colors.danger
    : severity === 'caution'
      ? colors.warning
      : colors.ink3;

  const eyebrow = useMemo(() => {
    if (!current) return null;
    return {
      sev: severity.toUpperCase(),
      tail: remaining !== null ? `AUTO-DENY IN ${remaining}S` : null,
    };
  }, [current, remaining, severity]);

  const deny = () => respond('deny');

  return (
    <Sheet open={!!current} onClose={deny} maxHeight="78%" hideHeader>
      {current ? (
        <View style={{ paddingHorizontal: space.s8, paddingTop: space.s1, paddingBottom: space.s8, gap: space.s6 }}>
          <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: space.s5 }}>
            <View style={{ flex: 1, gap: space.s2 }}>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center' }}>
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.danger, letterSpacing: 0.6 }}>
                  ALERT
                </Text>
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink4, letterSpacing: 0.6 }}>
                  {' · '}
                </Text>
                <View style={{ paddingRight: space.s2 }}>
                  <Diamond color={colors.danger} />
                </View>
                {current.profile ? (
                  <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink2, letterSpacing: 0.6 }}>
                    {`@${current.profile.toUpperCase()}`}
                  </Text>
                ) : null}
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink4, letterSpacing: 0.6 }}>
                  {' · '}
                </Text>
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3, letterSpacing: 0.6 }}>
                  SHELL
                </Text>
                {eyebrow.tail ? (
                  <>
                    <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink4, letterSpacing: 0.6 }}>
                      {' · '}
                    </Text>
                    <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3, letterSpacing: 0.6 }}>
                      {eyebrow.tail}
                    </Text>
                  </>
                ) : null}
              </View>
              <Text
                style={{
                  fontFamily: fonts.sans.bold,
                  fontSize: fontSizes.lg,
                  lineHeight: fontSizes.lg * lineHeights.normal,
                  color: colors.ink,
                }}
              >
                Allow this command?
              </Text>
            </View>
          </View>

          <View style={{ gap: space.s1 }}>
            <ScrollView
              style={{
                maxHeight: 160,
                backgroundColor: colors.bgInput,
                borderRadius: radii['3xl'],
                borderWidth: 0.5,
                borderColor: colors.line2,
              }}
              contentContainerStyle={{ paddingVertical: space.s5, paddingHorizontal: space.s6 }}
            >
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.lg, color: colors.ink }}>
                {current.command}
              </Text>
            </ScrollView>

            {current.cwd ? (
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
                cwd <Text style={{ color: colors.ink2 }}>{current.cwd}</Text>
              </Text>
            ) : null}
          </View>

          <View>
            {ALLOW_CHOICES.map((c) => (
              <Pressable
                key={c.value}
                disabled={busy}
                onPress={() => respond(c.value)}
                style={({ pressed }) => ({
                  paddingVertical: space.s5,
                  paddingHorizontal: space.s5,
                  borderRadius: radii.lg,
                  backgroundColor: pressed ? colors.hover : 'transparent',
                  opacity: busy ? 0.5 : 1,
                })}
              >
                <Text
                  style={{
                    fontFamily: fonts.sans.semibold,
                    fontSize: fontSizes.lg,
                    lineHeight: fontSizes.lg * lineHeights.normal,
                    color: colors.ink,
                  }}
                >
                  {c.label}
                </Text>
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3 }}>
                  {c.hint}
                </Text>
              </Pressable>
            ))}
          </View>

          <Pressable
            disabled={busy}
            onPress={deny}
            style={({ pressed }) => ({
              alignSelf: 'stretch',
              paddingVertical: space.s6,
              borderRadius: radii.lg,
              backgroundColor: colors.danger,
              alignItems: 'center',
              opacity: busy ? 0.4 : pressed ? 0.85 : 1,
            })}
          >
            <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.bgPane }}>
              Deny
            </Text>
          </Pressable>

          {error ? (
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.danger }}>
              {error}
            </Text>
          ) : null}
        </View>
      ) : null}
    </Sheet>
  );
}

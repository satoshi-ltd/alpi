import { Pressable, ScrollView, Text, View } from 'react-native';
import { fonts, radii, space , fontSizes} from '../../theme/tokens';

import { Sheet } from '../../components/Sheet';
import { Dot } from '../../components/Dot';
import { useTheme } from '../../theme/ThemeContext';

function mix(hex, pct, base) {
  const fromHex = (h) => {
    if (typeof h !== 'string' || !h.startsWith('#') || h.length < 7) return [120, 120, 120];
    const v = h.slice(1);
    return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
  };
  const [r1, g1, b1] = fromHex(hex);
  const [r2, g2, b2] = fromHex(base);
  const r = Math.round(r1 * pct + r2 * (1 - pct));
  const g = Math.round(g1 * pct + g2 * (1 - pct));
  const b = Math.round(b1 * pct + b2 * (1 - pct));
  return `rgb(${r},${g},${b})`;
}

const CLOSED = new Set(['done', 'skipped', 'blocked', 'preempted']);

function StatusIcon({ status, accent, colors }) {
  if (status === 'done') {
    return <Text style={{ color: accent, fontSize: fontSizes.xl, lineHeight: 18, fontFamily: fonts.sans.bold }}>✓</Text>;
  }
  if (status === 'blocked') {
    return (
      <Text style={{ color: colors.danger, fontSize: fontSizes.xl, lineHeight: 18, fontFamily: fonts.sans.bold }}>
        ⨯
      </Text>
    );
  }
  if (status === 'skipped' || status === 'preempted') {
    return (
      <View
        style={{
          width: 14,
          height: 14,
          borderRadius: radii.sm,
          borderWidth: 1.6,
          borderColor: colors.warning,
          overflow: 'hidden',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <View
          style={{
            position: 'absolute',
            width: 18,
            height: 1.6,
            backgroundColor: colors.warning,
            transform: [{ rotate: '45deg' }],
          }}
        />
      </View>
    );
  }
  return <Dot color={accent ?? colors.ink3} pulse />;
}

export function TasksSheet({ open, onClose, tasks = [], workgroupId, accent, onPick }) {
  const { colors, fonts, fontSizes } = useTheme();
  const closed = tasks.filter((t) => CLOSED.has(t.status)).length;
  const total = tasks.length;
  const hasActive = tasks.some((t) => !CLOSED.has(t.status));

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={hasActive ? 'Active task' : 'All resolved'}
      subtitle={`${closed}/${total} closed · #${workgroupId ?? ''}`}
    >
      <View style={{ paddingHorizontal: space.s8, paddingTop: space.s3, paddingBottom: space.s5 }}>
        <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3, lineHeight: fontSizes.sm * 1.45 }}>
          The hub opens one{' '}
          <Text style={{ fontFamily: fonts.mono, color: colors.ink2, backgroundColor: colors.hover }}>{' #task '}</Text>
          at a time and closes with{' '}
          <Text style={{ fontFamily: fonts.mono, color: colors.ink2, backgroundColor: colors.hover }}>{' #done '}</Text>
          or{' '}
          <Text style={{ fontFamily: fonts.mono, color: colors.ink2, backgroundColor: colors.hover }}>{' #skip '}</Text>
          .
        </Text>
      </View>
      <ScrollView contentContainerStyle={{ paddingBottom: space.s7 }}>
        {tasks.length === 0 ? (
          <View style={{ padding: space.s9, alignItems: 'center' }}>
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3 }}>
              No tasks yet — direct the hub to open one.
            </Text>
          </View>
        ) : (
          tasks.map((t) => {
            const isSoft = t.status === 'skipped' || t.status === 'preempted';
            const isBlocked = t.status === 'blocked';
            const statusLabel = CLOSED.has(t.status) ? t.status : 'working';
            const statusColor = isBlocked
              ? colors.danger
              : isSoft
                ? colors.warning
                : mix(accent ?? colors.ink3, 0.7, colors.ink3);
            return (
              <Pressable
                key={t.id}
                onPress={() => {
                  onPick?.(t.seq);
                  onClose?.();
                }}
                android_ripple={{ color: colors.selected }}
                style={({ pressed }) => ({
                  flexDirection: 'row',
                  alignItems: 'flex-start',
                  gap: space.s6,
                  paddingHorizontal: space.s8,
                  paddingVertical: space.s5,
                  backgroundColor: pressed ? colors.selected : 'transparent',
                })}
              >
                <View style={{ width: 24, height: fontSizes.md * 1.3, alignItems: 'center', justifyContent: 'center' }}>
                  <StatusIcon status={t.status} accent={accent} colors={colors} />
                </View>
                <View style={{ flex: 1, gap: space.s1 }}>
                  <Text
                    style={{
                      fontFamily: fonts.sans.semibold,
                      fontSize: fontSizes.md,
                      color: colors.ink,
                      lineHeight: fontSizes.md * 1.3,
                    }}
                  >
                    {t.title || `#${t.id}`}
                  </Text>
                  <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: space.s3 }}>
                    <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
                      #{t.id}
                    </Text>
                    <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>·</Text>
                    <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
                      {t.msgs} msg{t.msgs === 1 ? '' : 's'}
                    </Text>
                    <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>·</Text>
                    <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: statusColor }}>
                      {statusLabel}
                    </Text>
                  </View>
                </View>
              </Pressable>
            );
          })
        )}
      </ScrollView>
    </Sheet>
  );
}

import { useEffect, useRef } from 'react';
import { Animated, Pressable, ScrollView, Text, View } from 'react-native';
import { fonts, radii, space , fontSizes} from '../../theme/tokens';

import { Hash } from '../../components/Hash';
import { accentForProfile } from '../../theme/accents';
import { useTheme } from '../../theme/ThemeContext';
import { ThinkingDots } from '../chat/ThinkingDots';

function mixHex(hex, pct, base) {
  const fromHex = (h) => {
    const v = h.replace('#', '');
    return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
  };
  const [r1, g1, b1] = fromHex(hex);
  const [r2, g2, b2] = fromHex(base);
  const r = Math.round(r1 * pct + r2 * (1 - pct));
  const g = Math.round(g1 * pct + g2 * (1 - pct));
  const b = Math.round(b1 * pct + b2 * (1 - pct));
  return `rgb(${r},${g},${b})`;
}

function alpha(hex, a) {
  const v = hex.replace('#', '');
  const aHex = Math.round(a * 255)
    .toString(16)
    .padStart(2, '0');
  return `#${v}${aHex}`;
}

function Pip({ kind, color, count, bg }) {
  if (kind === 'working') {
    return (
      <View
        style={{
          position: 'absolute',
          bottom: -1,
          right: -1,
          width: 16,
          height: 16,
          borderRadius: radii.sm,
          backgroundColor: bg,
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <ThinkingDots color={color} />
      </View>
    );
  }
  if (kind === 'unread' && count) {
    return (
      <View
        style={{
          position: 'absolute',
          top: -2,
          right: -2,
          minWidth: 16,
          height: 16,
          paddingHorizontal: space.s1,
          borderRadius: radii.sm,
          backgroundColor: color,
          borderWidth: 1.5,
          borderColor: bg,
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Text style={{ color: '#fff', fontSize: fontSizes.xxs, fontFamily: fonts.sans.semibold, lineHeight: 13 }}>{count}</Text>
      </View>
    );
  }
  return null;
}

export function PinnedRow({ items, onPress, onLongPress }) {
  const { colors, fonts , fontSizes} = useTheme();
  // Always render the container so tab/filter changes don't shift the layout below.
  const hasItems = !!items?.length;
  return (
    <View style={{ minHeight: hasItems ? undefined : 0 }}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ paddingHorizontal: space.s7, paddingTop: space.s1, paddingBottom: space.s6, gap: space.s6 }}
      >
        {(items ?? []).map((it) => {
          const isWg = it.kind === 'workgroup';
          // it.accent is set upstream (useInbox) — wg items borrow the hub profile's accent.
          const accent = it.accent ?? accentForProfile(it.id ?? it.name);
          const needsProvider = !!it.needsProvider && !isWg;
          const tint = needsProvider
            ? 'transparent'
            : mixHex(accent, 0.18, colors.bgPane);
          const borderColor = needsProvider ? alpha(accent, 0.5) : alpha(accent, 0.3);
          const labelText = it.label ?? it.name ?? it.id;

          return (
            <Pressable
              key={`${it.kind}:${isWg ? `${it.profile}/` : ''}${it.id}`}
              onPress={() => onPress?.(it)}
              onLongPress={() => onLongPress?.(it)}
              style={({ pressed }) => ({
                alignItems: 'center',
                gap: space.s2,
                width: 60,
                opacity: pressed ? 0.7 : needsProvider ? 0.55 : 1,
              })}
            >
              <View
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: 26,
                  backgroundColor: tint,
                  borderWidth: needsProvider ? 1.5 : 0.5,
                  borderColor,
                  borderStyle: needsProvider ? 'dashed' : 'solid',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {isWg ? (
                  <Hash color={accent} size={26} />
                ) : needsProvider ? (
                  <View
                    style={{
                      width: 16,
                      height: 16,
                      transform: [{ rotate: '45deg' }],
                      borderRadius: 2,
                      borderWidth: 1.5,
                      borderColor: accent,
                    }}
                  />
                ) : (
                  <View
                    style={{
                      width: 18,
                      height: 18,
                      transform: [{ rotate: '45deg' }],
                      borderRadius: 3,
                      backgroundColor: accent,
                    }}
                  />
                )}
                {it.state === 'working' ? <Pip kind="working" color={accent} bg={colors.bg} /> : null}
                {it.unread && it.state !== 'working' ? (
                  <Pip kind="unread" count={it.unread} color={colors.accent} bg={colors.bg} />
                ) : null}
              </View>
              <Text
                numberOfLines={1}
                style={{
                  fontFamily: fonts.sans.medium,
                  fontSize: fontSizes.xs,
                  lineHeight: 13,
                  color: colors.ink2,
                  maxWidth: 60,
                }}
              >
                {labelText}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

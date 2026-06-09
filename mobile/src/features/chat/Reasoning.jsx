import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';
import { lineHeights, space } from '../../theme/tokens';

function toParagraphs(text) {
  return String(text || '')
    .split(/\n{2,}/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function fmtDuration(s) {
  const n = Math.round(s);
  if (n < 60) return `${n}s`;
  const m = Math.floor(n / 60);
  const r = n % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}

export function Reasoning({ text, seconds, streaming = false }) {
  const { colors, fonts, fontSizes } = useTheme();
  const paras = toParagraphs(text);
  const [open, setOpen] = useState(streaming);
  if (!paras.length) return null;
  const label = streaming
    ? 'Reasoning…'
    : seconds >= 1
      ? `Reasoned for ${fmtDuration(seconds)}`
      : 'Reasoned';
  return (
    <View>
      <Pressable
        onPress={() => setOpen((v) => !v)}
        hitSlop={8}
        style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}
        accessibilityLabel={open ? 'Collapse reasoning' : 'Expand reasoning'}
      >
        <View style={{ transform: [{ rotate: open ? '0deg' : '-90deg' }] }}>
          <Icon name="chevron-down" size={14} color={colors.ink3} />
        </View>
        <Text style={{ color: colors.ink3, fontFamily: fonts.sans.regular, fontSize: fontSizes.base }}>
          {label}
        </Text>
      </Pressable>
      {open ? (
        <View style={{ marginTop: space.s2, paddingLeft: space.s4, borderLeftWidth: 1, borderLeftColor: colors.line }}>
          {paras.map((p, i) => (
            <Text
              key={i}
              style={{
                color: colors.ink3,
                fontFamily: fonts.sans.regular,
                fontSize: fontSizes.base,
                lineHeight: fontSizes.base * lineHeights.normal,
                marginBottom: i < paras.length - 1 ? space.s3 : 0,
              }}
            >
              {p}
            </Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}

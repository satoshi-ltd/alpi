import { Text, View } from 'react-native';
import { space , fontSizes} from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';

function parseInline(text, key, theme) {
  const out = [];
  const re = /\*\*([^*]+)\*\*|`([^`]+)`/g;
  let last = 0;
  let m;
  let idx = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push({ key: `${key}-t-${idx++}`, text: text.slice(last, m.index) });
    if (m[1]) out.push({ key: `${key}-b-${idx++}`, text: m[1], bold: true });
    else if (m[2]) out.push({ key: `${key}-c-${idx++}`, text: m[2], code: true });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ key: `${key}-t-${idx++}`, text: text.slice(last) });
  return out.map((seg) =>
    seg.bold ? (
      <Text key={seg.key} style={{ fontFamily: theme.fonts.sans.semibold, color: theme.colors.ink }}>
        {seg.text}
      </Text>
    ) : seg.code ? (
      <Text
        key={seg.key}
        style={{
          fontFamily: theme.fonts.mono,
          fontSize: fontSizes.md,
          backgroundColor: theme.colors.hover,
          color: theme.colors.ink,
        }}
      >
        {' '}
        {seg.text}{' '}
      </Text>
    ) : (
      <Text key={seg.key}>{seg.text}</Text>
    ),
  );
}

export function RichText({ children, color, size }) {
  const theme = useTheme();
  const { colors, fonts } = theme;
  const fg = color ?? colors.ink;
  const fz = size ?? 16;
  const lh = fz * 1.55;
  const lines = (children ?? '').split('\n');
  const blocks = [];

  let listBuf = null;
  const flushList = (k) => {
    if (!listBuf) return;
    blocks.push(
      <View key={`l-${k}`} style={{ marginVertical: space.s2, paddingLeft: space.s8, gap: space.s1 }}>
        {listBuf.map((item, i) => (
          <View key={i} style={{ flexDirection: 'row', gap: space.s3 }}>
            <Text style={{ color: fg, fontSize: fz, lineHeight: lh }}>•</Text>
            <Text style={{ flex: 1, color: fg, fontSize: fz, lineHeight: lh, fontFamily: fonts.sans.regular }}>
              {parseInline(item, `l${k}-${i}`, theme)}
            </Text>
          </View>
        ))}
      </View>,
    );
    listBuf = null;
  };

  lines.forEach((raw, i) => {
    const line = raw.trimEnd();
    if (!line.trim()) {
      flushList(i);
      blocks.push(<View key={`s-${i}`} style={{ height: 8 }} />);
      return;
    }
    const h3 = /^### (.+)$/.exec(line);
    const h2 = /^## (.+)$/.exec(line);
    const h1 = /^# (.+)$/.exec(line);
    if (h1 || h2 || h3) {
      flushList(i);
      const txt = (h1 || h2 || h3)[1];
      blocks.push(
        <Text
          key={`h-${i}`}
          style={{
            fontFamily: fonts.sans.semibold,
            fontSize: fontSizes.msg,
            lineHeight: 16 * 1.2,
            color: colors.ink,
            marginTop: space.s6,
            marginBottom: space.s1,
            letterSpacing: -0.16,
          }}
        >
          {parseInline(txt, `h${i}`, theme)}
        </Text>,
      );
      return;
    }
    const li = /^[-*] (.+)$/.exec(line);
    if (li) {
      if (!listBuf) listBuf = [];
      listBuf.push(li[1]);
      return;
    }
    flushList(i);
    blocks.push(
      <Text
        key={`p-${i}`}
        style={{ color: fg, fontSize: fz, lineHeight: lh, fontFamily: fonts.sans.regular }}
      >
        {parseInline(line, `p${i}`, theme)}
      </Text>,
    );
  });
  flushList('end');

  return <View>{blocks}</View>;
}

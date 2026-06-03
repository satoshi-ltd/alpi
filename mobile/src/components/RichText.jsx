import { ScrollView, Text, View } from 'react-native';
import { space, fontSizes, lineHeights, radii } from '../theme/tokens';

import { segmentBlocks } from '../lib/markdownBlocks';
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

function CodeBlock({ lang, code, theme }) {
  const { colors, fonts } = theme;
  return (
    <View
      style={{
        marginVertical: space.s3,
        borderRadius: radii.md,
        borderWidth: 0.5,
        borderColor: colors.line,
        backgroundColor: colors.hover,
        overflow: 'hidden',
      }}
    >
      <View
        style={{
          paddingHorizontal: space.s4,
          paddingVertical: space.s2,
          borderBottomWidth: 0.5,
          borderBottomColor: colors.line,
        }}
      >
        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
          {lang || 'text'}
        </Text>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ padding: space.s5 }}>
        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.md, color: colors.ink, lineHeight: fontSizes.md * 1.5 }}>
          {code}
        </Text>
      </ScrollView>
    </View>
  );
}

function MdTable({ header, rows, theme }) {
  const { colors, fonts } = theme;
  const cols = header.length;
  // RN has no table auto-layout: fix each column's width from its widest cell so
  // header/rows align, then scroll horizontally instead of compressing.
  const colWidths = Array.from({ length: cols }, (_, j) => {
    const longest = Math.max(
      String(header[j] ?? '').length,
      ...rows.map((r) => String(r[j] ?? '').length),
    );
    return Math.min(200, Math.max(64, longest * 7 + 24));
  });
  const cellBase = { paddingHorizontal: space.s4, paddingVertical: space.s3 };
  return (
    <View
      style={{
        marginVertical: space.s3,
        borderRadius: radii.md,
        borderWidth: 0.5,
        borderColor: colors.line2,
        overflow: 'hidden',
      }}
    >
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View>
          <View style={{ flexDirection: 'row', backgroundColor: colors.hover, borderBottomWidth: 0.5, borderBottomColor: colors.line }}>
            {header.map((c, j) => (
              <Text
                key={j}
                style={[cellBase, { width: colWidths[j], fontFamily: fonts.sans.semibold, fontSize: fontSizes.sm, color: colors.ink2 }]}
              >
                {parseInline(c, `th-${j}`, theme)}
              </Text>
            ))}
          </View>
          {rows.map((row, r) => (
            <View
              key={r}
              style={{
                flexDirection: 'row',
                borderBottomWidth: r < rows.length - 1 ? 0.5 : 0,
                borderBottomColor: colors.line,
              }}
            >
              {Array.from({ length: cols }).map((_, j) => (
                <Text
                  key={j}
                  style={[cellBase, { width: colWidths[j], fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink, lineHeight: fontSizes.sm * 1.5 }]}
                >
                  {parseInline(row[j] ?? '', `td-${r}-${j}`, theme)}
                </Text>
              ))}
            </View>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

export function RichText({ children, color, size }) {
  const theme = useTheme();
  const { colors, fonts } = theme;
  const fg = color ?? colors.ink;
  const fz = size ?? 16;
  const lh = fz * 1.55;

  return (
    <View>
      {segmentBlocks(children).map((b, i) => {
        if (b.type === 'code') return <CodeBlock key={`code-${i}`} lang={b.lang} code={b.code} theme={theme} />;
        if (b.type === 'table') return <MdTable key={`tbl-${i}`} header={b.header} rows={b.rows} theme={theme} />;
        if (b.type === 'space') return <View key={`s-${i}`} style={{ height: 8 }} />;
        if (b.type === 'heading') {
          return (
            <Text
              key={`h-${i}`}
              style={{
                fontFamily: fonts.sans.semibold,
                fontSize: fontSizes.lg,
                lineHeight: fontSizes.lg * lineHeights.cozy,
                color: colors.ink,
                marginTop: space.s6,
                marginBottom: space.s1,
                letterSpacing: -0.16,
              }}
            >
              {parseInline(b.text, `h${i}`, theme)}
            </Text>
          );
        }
        if (b.type === 'list') {
          return (
            <View key={`l-${i}`} style={{ marginVertical: space.s2, paddingLeft: space.s8, gap: space.s1 }}>
              {b.items.map((item, j) => (
                <View key={j} style={{ flexDirection: 'row', gap: space.s3 }}>
                  <Text style={{ color: fg, fontSize: fz, lineHeight: lh }}>•</Text>
                  <Text style={{ flex: 1, color: fg, fontSize: fz, lineHeight: lh, fontFamily: fonts.sans.regular }}>
                    {parseInline(item, `l${i}-${j}`, theme)}
                  </Text>
                </View>
              ))}
            </View>
          );
        }
        return (
          <Text
            key={`p-${i}`}
            style={{ color: fg, fontSize: fz, lineHeight: lh, fontFamily: fonts.sans.regular }}
          >
            {parseInline(b.text, `p${i}`, theme)}
          </Text>
        );
      })}
    </View>
  );
}

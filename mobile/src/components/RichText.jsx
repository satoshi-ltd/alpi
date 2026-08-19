import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Image, Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { space, lineHeights, radii } from '../theme/tokens';

import { SheetClose } from './SheetClose';
import { segmentBlocks } from '../lib/markdownBlocks';
import { useCachedImage } from '../hooks/useCachedImage';
import { useEndpoint } from '../lib/EndpointContext';
import { useTheme } from '../theme/ThemeContext';

function MarkdownImage({ path, alt, note, profile, theme }) {
  const { colors, fonts, fontSizes } = theme;
  const { call, endpoint } = useEndpoint();
  const { uri } = useCachedImage(call, endpoint, profile, path);
  const [aspect, setAspect] = useState(16 / 9);
  const [open, setOpen] = useState(false);
  const filename = path.split('/').pop();
  const caption = note ? `${filename} · ${note}` : filename;

  useEffect(() => {
    if (uri) Image.getSize(uri, (w, h) => h && setAspect(w / h), () => {});
  }, [uri]);

  return (
    <View style={{ marginVertical: space.s3 }}>
      <Pressable onPress={() => uri && setOpen(true)} disabled={!uri}>
        {uri ? (
          <Image
            source={{ uri }}
            style={{ width: '100%', aspectRatio: aspect, borderRadius: radii.lg, borderWidth: 0.5, borderColor: colors.line, backgroundColor: colors.hover }}
            resizeMode="cover"
            accessibilityLabel={alt}
          />
        ) : (
          <View style={{ height: 160, borderRadius: radii.lg, borderWidth: 0.5, borderColor: colors.line, backgroundColor: colors.hover, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        )}
      </Pressable>
      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3, marginTop: space.s2 }}>
        {caption}
      </Text>
      <Modal
        visible={open}
        transparent
        animationType="fade"
        supportedOrientations={['portrait', 'landscape-left', 'landscape-right']}
        onRequestClose={() => setOpen(false)}
      >
        <Pressable
          onPress={() => setOpen(false)}
          style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.85)', alignItems: 'center', justifyContent: 'center', padding: space.s5 }}
        >
          <SheetClose
            onPress={() => setOpen(false)}
            color="rgba(255,255,255,0.82)"
            hint="Dismisses the image — you can also tap the backdrop"
            style={{ position: 'absolute', top: space.s11, right: space.s7 }}
          />
          {uri ? <Image source={{ uri }} style={{ width: '100%', height: '80%' }} resizeMode="contain" /> : null}
          {caption ? (
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: 'rgba(255,255,255,0.82)', marginTop: space.s4 }}>
              {caption}
            </Text>
          ) : null}
        </Pressable>
      </Modal>
    </View>
  );
}

function parseInline(text, key, theme, opts = {}) {
  const fg = opts.color ?? theme.colors.ink;
  const codeColor = opts.codeColor ?? fg;
  const codeBackground = opts.codeBackground ?? theme.colors.hover;
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
      <Text key={seg.key} style={{ fontFamily: theme.fonts.sans.semibold, color: fg }}>
        {seg.text}
      </Text>
    ) : seg.code ? (
      <Text
        key={seg.key}
        style={{
          fontFamily: theme.fonts.mono,
          fontSize: theme.fontSizes.md,
          backgroundColor: codeBackground,
          color: codeColor,
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
  const { colors, fonts, fontSizes } = theme;
  return (
    <View
      style={{
        marginVertical: space.s3,
        borderRadius: radii.lg,
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
        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.md, color: colors.ink, lineHeight: fontSizes.md * lineHeights.normal }}>
          {code}
        </Text>
      </ScrollView>
    </View>
  );
}

function MdTable({ header, rows, theme, inlineOpts }) {
  const { colors, fonts, fontSizes } = theme;
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
        borderRadius: radii.lg,
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
                {parseInline(c, `th-${j}`, theme, inlineOpts)}
              </Text>
            ))}
          </View>
          {rows.map((row, r) => (
            <View
              key={r}
              style={{
                flexDirection: 'row',
                backgroundColor: colors.bg,
                borderBottomWidth: r < rows.length - 1 ? 0.5 : 0,
                borderBottomColor: colors.line,
              }}
            >
              {Array.from({ length: cols }).map((_, j) => (
                <Text
                  key={j}
                  style={[cellBase, { width: colWidths[j], fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink, lineHeight: fontSizes.sm * lineHeights.normal }]}
                >
                  {parseInline(row[j] ?? '', `td-${r}-${j}`, theme, inlineOpts)}
                </Text>
              ))}
            </View>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

export function RichText({ children, color, size, imageProfile, codeColor, codeBackground }) {
  const theme = useTheme();
  const { colors, fonts, fontSizes } = theme;
  const fg = color ?? colors.ink;
  const fz = size ?? fontSizes.lg;
  const lh = fz * 1.55;
  const blocks = useMemo(() => segmentBlocks(children), [children]);
  const inlineOpts = { color: fg, codeColor, codeBackground };

  return (
    <View>
      {blocks.map((b, i) => {
        if (b.type === 'code') return <CodeBlock key={`code-${i}`} lang={b.lang} code={b.code} theme={theme} />;
        if (b.type === 'table') return <MdTable key={`tbl-${i}`} header={b.header} rows={b.rows} theme={theme} inlineOpts={inlineOpts} />;
        if (b.type === 'image') return <MarkdownImage key={`img-${i}`} path={b.path} alt={b.alt} note={b.note} profile={imageProfile} theme={theme} />;
        if (b.type === 'space') return <View key={`s-${i}`} style={{ height: 8 }} />;
        if (b.type === 'heading') {
          return (
            <Text
              key={`h-${i}`}
              style={{
                fontFamily: fonts.sans.semibold,
                fontSize: fontSizes.lg,
                lineHeight: fontSizes.lg * lineHeights.cozy,
                color: fg,
                marginTop: space.s6,
                marginBottom: space.s1,
                letterSpacing: -0.16,
              }}
            >
              {parseInline(b.text, `h${i}`, theme, inlineOpts)}
            </Text>
          );
        }
        if (b.type === 'quote') {
          return (
            <View
              key={`q-${i}`}
              style={{
                borderLeftWidth: 3,
                borderLeftColor: fg,
                paddingLeft: space.s4,
                marginVertical: space.s2,
                opacity: 0.85,
              }}
            >
              <Text style={{ color: fg, fontSize: fz, lineHeight: lh, fontFamily: fonts.sans.regular }}>
                {parseInline(b.text, `q${i}`, theme, inlineOpts)}
              </Text>
            </View>
          );
        }
        if (b.type === 'list') {
          return (
            <View key={`l-${i}`} style={{ marginVertical: space.s2, paddingLeft: space.s8, gap: space.s1 }}>
              {b.items.map((item, j) => (
                <View key={j} style={{ flexDirection: 'row', gap: space.s3 }}>
                  <Text style={{ color: fg, fontSize: fz, lineHeight: lh, fontFamily: fonts.sans.regular }}>•</Text>
                  <Text style={{ flex: 1, color: fg, fontSize: fz, lineHeight: lh, fontFamily: fonts.sans.regular }}>
                    {parseInline(item, `l${i}-${j}`, theme, inlineOpts)}
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
            {parseInline(b.text, `p${i}`, theme, inlineOpts)}
          </Text>
        );
      })}
    </View>
  );
}

import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { Eyebrow } from './Eyebrow';
import { groupTone } from './groupTone';
import { Icon } from './Icon';
import { errorParts, failedTitle, inlineSegments, parseNotificationBody } from '../../../common/notificationBody.mjs';
import { useTheme } from '../theme/ThemeContext';
import { lineHeights, radii, space } from '../theme/tokens';

function topMargin(block, prev) {
  if (!prev) return 0;
  if (block.kind === 'heading') return space.s8;
  if (prev.kind === 'label' || prev.kind === 'heading') return space.s2;
  return space.s7;
}

function Lead({ text, theme }) {
  return (
    <Text style={{ fontFamily: theme.fonts.sans.semibold, fontSize: theme.fontSizes.xl, lineHeight: theme.fontSizes.xl * lineHeights.cozy, color: theme.colors.ink }}>
      <Inline text={text} theme={theme} />
    </Text>
  );
}

function Heading({ text, theme }) {
  return (
    <Text style={{ fontFamily: theme.fonts.sans.semibold, fontSize: theme.fontSizes.lg, lineHeight: theme.fontSizes.lg * lineHeights.cozy, color: theme.colors.ink }}>
      <Inline text={text} theme={theme} />
    </Text>
  );
}

function Para({ text, theme }) {
  return (
    <Text style={{ fontFamily: theme.fonts.sans.regular, fontSize: theme.fontSizes.md, lineHeight: theme.fontSizes.md * lineHeights.relaxed, color: theme.colors.ink2 }}>
      <Inline text={text} theme={theme} />
    </Text>
  );
}

function Quote({ text, theme }) {
  return (
    <View style={{ paddingLeft: space.s4, borderLeftWidth: 2, borderLeftColor: theme.colors.line2 }}>
      <Text style={{ fontFamily: theme.fonts.sans.regular, fontSize: theme.fontSizes.md, lineHeight: theme.fontSizes.md * lineHeights.relaxed, color: theme.colors.ink2, fontStyle: 'italic' }}>
        <Inline text={text} theme={theme} />
      </Text>
    </View>
  );
}

function Inline({ text, theme }) {
  return inlineSegments(text).map((seg, i) => {
    if (seg.t === 'bold') {
      return (
        <Text key={i} style={{ fontFamily: theme.fonts.sans.semibold, color: theme.colors.ink }}>
          {seg.v}
        </Text>
      );
    }
    if (seg.t === 'italic') {
      return (
        <Text key={i} style={{ fontStyle: 'italic' }}>
          {seg.v}
        </Text>
      );
    }
    if (seg.t === 'code') {
      return (
        <Text
          key={i}
          style={{
            fontFamily: theme.fonts.mono,
            fontSize: theme.fontSizes.md,
            backgroundColor: theme.colors.hover,
            color: theme.colors.ink,
          }}
        >
          {' '}
          {seg.v}
          {' '}
        </Text>
      );
    }
    return <Text key={i}>{seg.v}</Text>;
  });
}

function Entry({ entry, last, theme }) {
  return (
    <View style={{ gap: space.s1, paddingVertical: space.s4, borderBottomWidth: last ? 0 : 0.5, borderBottomColor: theme.colors.line }}>
      <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: space.s3 }}>
        <Text style={{ flexShrink: 0, fontFamily: theme.fonts.sans.semibold, fontSize: theme.fontSizes.md, lineHeight: theme.fontSizes.md * lineHeights.normal, color: theme.colors.ink }}>
          {entry.name}
        </Text>
        {entry.meta ? (
          <Text numberOfLines={1} style={{ flex: 1, fontFamily: theme.fonts.mono, fontSize: theme.fontSizes.xs, color: theme.colors.ink3 }}>
            {entry.meta}
          </Text>
        ) : null}
      </View>
      {entry.text ? (
        <Text style={{ fontFamily: theme.fonts.sans.regular, fontSize: theme.fontSizes.md, lineHeight: theme.fontSizes.md * lineHeights.normal, color: theme.colors.ink2 }}>
          <Inline text={entry.text} theme={theme} />
        </Text>
      ) : null}
    </View>
  );
}

function List({ block, theme }) {
  if (block.items.every((it) => it.entry)) {
    return (
      <View>
        {block.items.map((it, j) => <Entry key={j} entry={it.entry} last={j === block.items.length - 1} theme={theme} />)}
      </View>
    );
  }
  return (
    <View style={{ paddingLeft: space.s4, gap: space.s2 }}>
      {block.items.map((it, j) => (
        <View key={j} style={{ flexDirection: 'row', gap: space.s3 }}>
          <Text style={{ fontFamily: block.ordered ? theme.fonts.mono : theme.fonts.sans.regular, fontSize: theme.fontSizes.md, lineHeight: theme.fontSizes.md * lineHeights.normal, color: theme.colors.ink3, minWidth: block.ordered ? 18 : undefined }}>
            {it.marker}
          </Text>
          <Text style={{ flex: 1, fontFamily: theme.fonts.sans.regular, fontSize: theme.fontSizes.md, lineHeight: theme.fontSizes.md * lineHeights.normal, color: theme.colors.ink2 }}>
            <Inline text={it.text} theme={theme} />
          </Text>
        </View>
      ))}
    </View>
  );
}

function CodeBlock({ text, theme }) {
  return (
    <View
      style={{
        borderRadius: radii.xs,
        borderWidth: 0.5,
        borderColor: theme.colors.line,
        backgroundColor: theme.colors.hover,
        overflow: 'hidden',
      }}
    >
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ padding: space.s5 }}>
        <Text style={{ fontFamily: theme.fonts.mono, fontSize: theme.fontSizes.md, lineHeight: theme.fontSizes.md * lineHeights.normal, color: theme.colors.ink }}>
          {text}
        </Text>
      </ScrollView>
    </View>
  );
}

function ReportTable({ block, theme }) {
  const rows = [block.headers, ...block.rows];
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
      <View style={{ borderWidth: 0.5, borderColor: theme.colors.line, borderRadius: radii.xs, overflow: 'hidden' }}>
        {rows.map((row, i) => (
          <View
            key={i}
            style={{
              flexDirection: 'row',
              backgroundColor: i === 0 ? theme.colors.hover : 'transparent',
              borderTopWidth: i === 0 ? 0 : 0.5,
              borderTopColor: theme.colors.line,
            }}
          >
            {row.map((cell, j) => (
              <Text
                key={j}
                style={{
                  minWidth: 96,
                  paddingHorizontal: space.s4,
                  paddingVertical: space.s3,
                  borderLeftWidth: j === 0 ? 0 : 0.5,
                  borderLeftColor: theme.colors.line,
                  fontFamily: i === 0 ? theme.fonts.sans.semibold : theme.fonts.sans.regular,
                  fontSize: theme.fontSizes.sm,
                  lineHeight: theme.fontSizes.sm * lineHeights.normal,
                  color: i === 0 ? theme.colors.ink : theme.colors.ink2,
                }}
              >
                <Inline text={cell} theme={theme} />
              </Text>
            ))}
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

function renderBlock(block, theme) {
  switch (block.kind) {
    case 'heading': return <Heading text={block.text} theme={theme} />;
    case 'label': return <Eyebrow>{block.label}</Eyebrow>;
    case 'labelBody':
      return (
        <View style={{ gap: space.s1 }}>
          <Eyebrow>{block.label}</Eyebrow>
          <Para text={block.body} theme={theme} />
        </View>
      );
    case 'quote': return <Quote text={block.text} theme={theme} />;
    case 'code': return <CodeBlock text={block.text} theme={theme} />;
    case 'table': return <ReportTable block={block} theme={theme} />;
    case 'list': return <List block={block} theme={theme} />;
    default: return <Para text={block.text} theme={theme} />;
  }
}

export function NotificationBody({ body, lead = false }) {
  const theme = useTheme();
  let blocks = parseNotificationBody(body);
  if (!blocks.length) return null;

  let leadText = null;
  if (lead && blocks[0].kind === 'p') {
    leadText = blocks[0].text;
    blocks = blocks.slice(1);
  }

  let prev = leadText != null ? { kind: 'lead' } : null;
  const children = [];
  if (leadText != null) children.push(<Lead key="lead" text={leadText} theme={theme} />);
  blocks.forEach((block, i) => {
    const mt = children.length === 0 ? 0 : topMargin(block, prev);
    children.push(
      <View key={i} style={{ marginTop: mt }}>
        {renderBlock(block, theme)}
      </View>,
    );
    prev = block;
  });

  return <View>{children}</View>;
}

function Details({ blocks, theme }) {
  const [open, setOpen] = useState(false);
  return (
    <View style={{ borderRadius: radii.xs, backgroundColor: theme.colors.hover, overflow: 'hidden' }}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel="Details"
        onPress={() => setOpen((v) => !v)}
        style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2, minHeight: 44, paddingHorizontal: space.s5 }}
      >
        <Icon name={open ? 'chevron-down' : 'chevron-right'} size="sm" color={theme.colors.ink3} />
        <Text style={{ fontFamily: theme.fonts.mono, fontSize: theme.fontSizes.sm, color: theme.colors.ink2 }}>Details</Text>
      </Pressable>
      {open ? blocks.map((b, i) => (
        <ScrollView key={i} horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: space.s5, paddingBottom: space.s4 }}>
          <Text selectable style={{ fontFamily: theme.fonts.mono, fontSize: theme.fontSizes.sm, lineHeight: theme.fontSizes.sm * lineHeights.normal, color: theme.colors.ink2 }}>
            {b.text}
          </Text>
        </ScrollView>
      )) : null}
    </View>
  );
}

export function ErrorCard({ title, body, actions = null }) {
  const theme = useTheme();
  const { colors, fonts, fontSizes, mode } = theme;
  const { lead, failed } = failedTitle(title);
  const { facts, details, rest } = errorParts(parseNotificationBody(body));
  return (
    <View style={{ gap: space.s5, padding: space.s6, borderRadius: radii.xs, backgroundColor: groupTone(colors, mode) }}>
      <View accessibilityRole="header" style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
        <Icon name="triangle-alert" size="md" color={colors.danger} />
        <Text style={{ flex: 1, fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, lineHeight: fontSizes.lg * lineHeights.cozy, color: colors.ink }}>
          {lead ? lead : <Text style={{ color: colors.dangerText }}>Failed</Text>}
          {failed ? <Text style={{ color: colors.dangerText }}>{' failed'}</Text> : null}
        </Text>
      </View>
      {facts.length ? (
        <View>
          {facts.map((f, i) => (
            <View key={i} style={{ flexDirection: 'row', gap: space.s5, paddingVertical: space.s3, borderBottomWidth: i === facts.length - 1 ? 0 : 0.5, borderBottomColor: colors.line }}>
              <Text style={{ minWidth: 64, flexShrink: 0, paddingTop: 2, fontFamily: fonts.mono, fontSize: fontSizes.xs, letterSpacing: 0.6, color: colors.ink3 }}>
                {f.label.toUpperCase()}
              </Text>
              <Text selectable style={{ flex: 1, fontFamily: fonts.sans.regular, fontSize: fontSizes.md, lineHeight: fontSizes.md * lineHeights.normal, color: i === 0 ? colors.ink : colors.ink2 }}>
                <Inline text={f.body} theme={theme} />
              </Text>
            </View>
          ))}
        </View>
      ) : null}
      {rest.map((b, i) => <View key={i}>{renderBlock(b, theme)}</View>)}
      {details.length ? <Details blocks={details} theme={theme} /> : null}
      {actions ? <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.s3 }}>{actions}</View> : null}
    </View>
  );
}

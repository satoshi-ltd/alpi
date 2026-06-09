import { useEffect, useState } from 'react';
import { ActivityIndicator, Image, Pressable, Text, View } from 'react-native';

import { Icon } from '../../components/Icon';
import { useEndpoint } from '../../lib/EndpointContext';
import { useTheme } from '../../theme/ThemeContext';
import { radii, space } from '../../theme/tokens';
import { fileKind, fileTypeLabel, fmtSize, shouldFetchPreview } from '../../lib/fileKind';

const ICON = { code: 'file-code', text: 'file-text', file: 'file', image: 'file' };
const BOX = 32;
const MESSAGE_MAX = 4;
const imageCache = new Map();

function FetchedImage({ path, profile, name, colors }) {
  const { call, endpoint } = useEndpoint();
  const key = `${profile || ''}:${path}`;
  const [uri, setUri] = useState(() => imageCache.get(key) || null);
  const [aspect, setAspect] = useState(16 / 9);
  const [err, setErr] = useState(null);
  useEffect(() => {
    if (uri || !endpoint || !profile) return undefined;
    let alive = true;
    call(endpoint, 'host.attachments.fetch', { profile, path })
      .then((r) => {
        const u = r?.data_base64 ? `data:${r.mime};base64,${r.data_base64}` : null;
        if (u) imageCache.set(key, u);
        if (alive) (u ? setUri(u) : setErr('empty response'));
      })
      .catch((e) => {
        if (alive) setErr(String(e?.message || e));
      });
    return () => { alive = false; };
  }, [key, endpoint, profile]);
  useEffect(() => { if (uri) Image.getSize(uri, (w, h) => h && setAspect(w / h), () => {}); }, [uri]);
  if (!uri) {
    return (
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3, padding: space.s3, borderRadius: radii.md, backgroundColor: colors.hover }}>
        {err ? <Icon name="file" size={16} color={colors.ink3} /> : <ActivityIndicator color={colors.ink3} />}
        <Text numberOfLines={2} style={{ flexShrink: 1, color: colors.ink3 }}>
          {name}{err ? `  ·  ${err}` : ''}
        </Text>
      </View>
    );
  }
  return (
    <Image
      source={{ uri }}
      style={{ width: '100%', aspectRatio: aspect, borderRadius: radii.md, borderWidth: 0.5, borderColor: colors.line, backgroundColor: colors.hover }}
      resizeMode="cover"
      accessibilityLabel={name}
    />
  );
}

function Glyph({ kind, localUri, name, colors }) {
  if (kind === 'image' && localUri) {
    return <Image source={{ uri: localUri }} style={{ width: BOX, height: BOX, borderRadius: radii.sm }} accessibilityLabel={name} />;
  }
  return (
    <View style={{ width: BOX, height: BOX, borderRadius: radii.sm, backgroundColor: colors.hover, alignItems: 'center', justifyContent: 'center' }}>
      <Icon name={ICON[kind] || 'file'} size={16} color={colors.ink3} />
    </View>
  );
}

export function AttachmentCards({ items, onRemove, variant = 'composer', profile }) {
  const { colors, fonts, fontSizes } = useTheme();
  if (!items?.length) return null;
  const message = variant === 'message';
  const shown = message ? items.slice(0, MESSAGE_MAX) : items;
  const hidden = items.length - shown.length;
  return (
    <View
      style={
        message
          ? { gap: space.s2, width: '82%' }
          : { flexDirection: 'row', flexWrap: 'wrap', gap: space.s3 }
      }
    >
      {shown.map((a, i) => {
        const kind = fileKind(a.name, a.mime);
        if (shouldFetchPreview(a, { message, profile })) {
          return (
            <FetchedImage key={a.path || a.name || i} path={a.path} profile={profile} name={a.name} colors={colors} />
          );
        }
        const subtitle = message
          ? `${fileTypeLabel(a.name, a.mime)} · ${fmtSize(a.size)}`
          : fmtSize(a.size);
        return (
          <View
            key={a.path || a.name || i}
            style={{
              flexDirection: 'row', alignItems: 'center', gap: space.s3,
              paddingVertical: space.s2, paddingHorizontal: space.s4,
              borderRadius: radii.md,
              backgroundColor: message ? colors.hover : colors.bgPane,
              borderWidth: message ? 0 : 0.5,
              borderColor: colors.line2,
              maxWidth: message ? undefined : 240,
              flexGrow: message ? 1 : 0,
            }}
          >
            <Glyph kind={kind} localUri={a.localUri} name={a.name} colors={colors} />
            <View style={{ flexShrink: 1, flexGrow: 1 }}>
              <Text numberOfLines={1} style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink }}>{a.name}</Text>
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>{subtitle}</Text>
            </View>
            {!message && onRemove ? (
              <Pressable onPress={() => onRemove(i)} hitSlop={8} accessibilityLabel={`Remove ${a.name}`}>
                <Icon name="x" size={14} color={colors.ink3} />
              </Pressable>
            ) : null}
          </View>
        );
      })}
      {hidden > 0 ? (
        <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, color: colors.ink3, paddingHorizontal: space.s2 }}>
          +{hidden} more file{hidden > 1 ? 's' : ''}
        </Text>
      ) : null}
    </View>
  );
}

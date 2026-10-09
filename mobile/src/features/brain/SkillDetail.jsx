import { useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { lineHeights, radii, space } from '../../theme/tokens';

import { AlertBanner } from '../../components/AlertBanner';
import { useAttention } from '../../hooks/useAttention';
import { skillBanner, skillItem } from '../../../../common/attention.mjs';
import { Icon } from '../../components/Icon';
import { RichText } from '../../components/RichText';
import { PanelHeader } from '../profile/PanelHeader';
import { StatusWord } from '../profile/StatusWord';
import { useEndpoint } from '../../lib/EndpointContext';
import { fileSize, flattenTree, statusLabel } from '../../lib/skillDetail';
import { skillFileIcon } from '../../../../common/fileKind.mjs';
import { useTheme } from '../../theme/ThemeContext';
import { Busy } from '../../components/Busy';
import { useBusyVisible } from '../../hooks/useBusyVisible';

export function SkillDetail({ profile: id, name, category, embedded = false, onBack }) {
  const router = useRouter();
  const { colors, fonts, fontSizes } = useTheme();
  const { call } = useEndpoint();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const holding = useBusyVisible(loading);
  const { att } = useAttention(id);

  useEffect(() => {
    if (!id || !name) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    const params = { profile: String(id), name: String(name) };
    if (category) params.category = String(category);
    call('host.skill.read', params)
      .then((r) => {
        if (cancelled) return;
        setDetail(r?.skill ?? null);
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setDetail(null);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id, name, category, call]);

  const flag = skillItem(att, detail?.category || (category ? String(category) : null), String(name));
  const banner = flag ? skillBanner(flag) : null;
  const status = detail ? statusLabel(detail.status) : null;
  const reason = detail?.reason ?? '';
  const requires = Array.isArray(detail?.requires) ? detail.requires : [];
  const tools = Array.isArray(detail?.tools) ? detail.tools : [];
  const files = useMemo(() => flattenTree(detail?.tree).filter((f) => f.path !== 'SKILL.md'), [detail?.tree]);
  const meta = { fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 };

  return (
    <View style={{ flex: 1 }}>
      {embedded ? null : <PanelHeader profile={id} section={category ? `SKILLS · ${String(category).toUpperCase()}` : 'SKILLS'} onBack={onBack} />}
      {loading || holding ? (
        <Busy fill visible={holding} label="Opening the skill" />
      ) : !detail ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s8 }}>
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink2 }}>
            Skill not found
          </Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s6, paddingBottom: space.s10 }}>
          {banner ? <AlertBanner {...banner} /> : null}
          <View style={{ gap: space.s3 }}>
            <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.xl, color: colors.ink }}>{detail.name ?? String(name)}</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s4, flexWrap: 'wrap' }}>
              <StatusWord word={status} on={status === 'active'} danger={status === 'invalid'} />
              {detail.version ? <Text style={meta}>v{detail.version}</Text> : null}
              <Text style={meta}>{detail.origin || 'agent'}</Text>
            </View>
          </View>

          {status !== 'active' && reason && !banner ? (
            <Text
              accessibilityRole="alert"
              style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * lineHeights.normal, color: status === 'invalid' ? colors.dangerText : colors.ink2 }}
            >
              {reason}
            </Text>
          ) : null}

          {detail.description ? (
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink, lineHeight: fontSizes.md * lineHeights.normal }}>
              {detail.description}
            </Text>
          ) : null}

          {tools.length > 0 ? (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.s2 }}>
              {tools.map((t) => (
                <View key={t} style={{ paddingHorizontal: space.s3, paddingVertical: 2, borderRadius: radii.xs, backgroundColor: colors.hover }}>
                  <Text style={meta}>{String(t).replace('__', '.')}</Text>
                </View>
              ))}
            </View>
          ) : null}

          {requires.length > 0 ? (
            <View style={{ gap: space.s2 }}>
              {requires.map((r) => (
                <View key={`${r.kind}:${r.name}`} style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
                  <StatusWord word={r.name} on={!!r.resolved} danger={!r.resolved} />
                  <Text style={meta}>{r.resolved ? r.kind : `${r.kind} · missing`}</Text>
                </View>
              ))}
            </View>
          ) : null}

          {files.length > 0 ? (
            <View style={{ borderRadius: radii.xs, backgroundColor: colors.bgPane ?? colors.hover, overflow: 'hidden' }}>
              {files.map((f, i) => {
                const openable = f.kind === 'file';
                const Wrapper = openable ? Pressable : View;
                return (
                  <Wrapper
                    key={f.path}
                    accessibilityRole={openable ? 'button' : undefined}
                    accessibilityLabel={f.path}
                    onPress={openable ? () => router.push({
                      pathname: `/profile/${id}/brain/skill-file`,
                      params: { name: String(name), category: category ? String(category) : '', file: f.path },
                    }) : undefined}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3, minHeight: 44, paddingHorizontal: space.s5, borderTopWidth: i ? 0.5 : 0, borderTopColor: colors.line }}
                  >
                    <Icon name={skillFileIcon(f)} size="sm" color={colors.ink2} />
                    <Text style={{ flex: 1, fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink }} numberOfLines={1}>{f.path}</Text>
                    <Text style={meta}>{f.locked ? `${f.count} · ${f.mode ?? ''}` : f.kind === 'file' ? fileSize(f.size) : ''}</Text>
                    {openable ? <Icon name="chevron-right" size="sm" color={colors.ink4 ?? colors.ink3} /> : null}
                  </Wrapper>
                );
              })}
            </View>
          ) : null}

          {detail.body ? (
            <RichText size={fontSizes.md} color={colors.ink}>{detail.body}</RichText>
          ) : (
            <Text style={meta}>(empty)</Text>
          )}
        </ScrollView>
      )}
    </View>
  );
}

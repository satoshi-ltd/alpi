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
import { useEndpoint } from '../../lib/EndpointContext';
import { flattenTree, skillVersion, statusLabel } from '../../lib/skillDetail';
import { sizeLabel } from '../../../../common/panelRow.mjs';
import { DetailHead } from '../../components/DetailHead';
import { FactCode, FactTable } from '../../components/FactTable';
import { skillFileIcon } from '../../../../common/fileKind.mjs';
import { useTheme } from '../../theme/ThemeContext';
import { Busy } from '../../components/Busy';
import { useBusyVisible } from '../../hooks/useBusyVisible';
import { code } from '../../theme/code';

function idList(names, missing = () => false) {
  return names.flatMap((n, i) => [
    i > 0 ? ', ' : null,
    <FactCode key={n} quiet={missing(n)}>{n}</FactCode>,
    missing(n) ? ' missing' : null,
  ]).filter(Boolean);
}

export function SkillDetail({ profile: id, name, category, embedded = false, onBack }) {
  const router = useRouter();
  const theme = useTheme();
  const { colors, fonts, fontSizes } = theme;
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
  const meta = { fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, color: colors.ink3 };

  return (
    <View style={{ flex: 1 }}>
      {embedded ? null : <PanelHeader profile={id} section={category ? `Skills · ${String(category)}` : 'Skills'} onBack={onBack} />}
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
          <DetailHead
            title={detail.name ?? String(name)}
            state={status}
            stateTone={status === 'invalid' ? 'danger' : null}
            id={detail.category ? `${detail.category}/${detail.name ?? String(name)}` : detail.name ?? String(name)}
          />

          {status !== 'active' && reason && !banner ? (
            <Text
              accessibilityRole="alert"
              style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * lineHeights.normal, color: status === 'invalid' ? colors.dangerText : colors.ink2 }}
            >
              {reason}
            </Text>
          ) : null}

          <FactTable
            rows={[
              { label: 'About', value: detail.description || null },
              { label: 'Requires', value: requires.length ? idList(requires.map((r) => r.name), (n) => requires.some((r) => r.name === n && !r.resolved)) : null },
              { label: 'Tools', value: tools.length ? idList(tools.map((t) => String(t).replace('__', '.'))) : null },
              { label: 'Keywords', value: Array.isArray(detail.keywords) && detail.keywords.length ? detail.keywords.join(', ') : null },
              { label: 'Version', value: skillVersion(detail) },
            ]}
          />

          {files.length > 0 ? (
            <View style={{ borderRadius: radii.surface, backgroundColor: colors.bgPane ?? colors.hover, overflow: 'hidden' }}>
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
                    style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3, minHeight: 44, paddingHorizontal: space.s5 }}
                  >
                    <Icon name={skillFileIcon(f)} size="xs" color={colors.ink2} />
                    <Text style={{ flex: 1, ...code(fonts, fontSizes.sm), color: colors.ink }} numberOfLines={1}>{f.path}</Text>
                    <Text style={meta}>{f.locked ? `${f.count} · ${f.mode ?? ''}` : f.kind === 'file' ? sizeLabel(f.size) : ''}</Text>
                    {openable ? <Icon name="chevron-right" size="xs" color={colors.ink4 ?? colors.ink3} /> : null}
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

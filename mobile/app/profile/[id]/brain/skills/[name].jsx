import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../../../src/theme/tokens';

import { ScreenHeader } from '../../../../../src/components/ScreenHeader';
import { useEndpoint } from '../../../../../src/lib/EndpointContext';
import { flattenTree, statusLabel } from '../../../../../src/lib/skillDetail';
import { useTheme } from '../../../../../src/theme/ThemeContext';

export default function SkillDetail() {
  const { id, name, path, category } = useLocalSearchParams();
  const router = useRouter();
  const { colors, fonts, fontSizes } = useTheme();
  const { call } = useEndpoint();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

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

  const subtitle = (category ? String(category).toUpperCase() : 'SKILL') + ` · @${id}`;
  const status = detail ? statusLabel(detail.status) : null;
  const reason = detail?.reason ?? '';
  const requires = Array.isArray(detail?.requires) ? detail.requires : [];
  const files = useMemo(() => flattenTree(detail?.tree), [detail?.tree]);

  const statusBg = status === 'active'
    ? colors.successBg ?? colors.hover
    : status === 'invalid' ? colors.dangerBg ?? colors.hover : colors.hover;
  const statusFg = status === 'active'
    ? colors.success ?? colors.ink2
    : status === 'invalid' ? colors.danger : colors.ink3;

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader title={String(name ?? 'Skill')} subtitle={subtitle} onBack={() => router.back()} />
      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.ink3} />
        </View>
      ) : !detail ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s8 }}>
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink2 }}>
            Skill not found
          </Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s5, paddingBottom: space.s10 }}>
          {(path || detail.path) ? (
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }} numberOfLines={1}>
              {String(path ?? detail.path)}
            </Text>
          ) : null}

          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3, flexWrap: 'wrap' }}>
            <View
              style={{
                paddingHorizontal: space.s3,
                paddingVertical: space.s1,
                borderRadius: space.s2,
                backgroundColor: statusBg,
              }}
              accessibilityRole="text"
              accessibilityLabel={`status ${status}`}
            >
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: statusFg, letterSpacing: 0.6 }}>
                {status?.toUpperCase()}
              </Text>
            </View>
            {detail.version ? (
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>v{detail.version}</Text>
            ) : null}
            {detail.origin ? (
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>· {detail.origin}</Text>
            ) : null}
          </View>

          {status !== 'active' && reason ? (
            <View
              style={{
                padding: space.s4,
                borderRadius: space.s2,
                borderWidth: 0.5,
                borderColor: status === 'invalid' ? colors.danger : colors.line,
                gap: space.s1,
              }}
              accessibilityRole="alert"
            >
              <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.sm, color: status === 'invalid' ? colors.danger : colors.ink2 }}>
                {status === 'invalid' ? 'Invalid' : 'Inactive'}
              </Text>
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3 }}>
                {reason}
              </Text>
            </View>
          ) : null}

          {detail.description ? (
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink, lineHeight: fontSizes.md * 1.5 }}>
              {detail.description}
            </Text>
          ) : null}

          {requires.length > 0 ? (
            <View style={{ gap: space.s2 }}>
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3, letterSpacing: 0.6 }}>
                REQUIRES
              </Text>
              {requires.map((r) => (
                <View key={`${r.kind}:${r.name}`} style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
                  <View
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 4,
                      backgroundColor: r.resolved ? (colors.success ?? colors.ink2) : colors.danger,
                    }}
                    accessibilityLabel={r.resolved ? 'resolved' : 'missing'}
                  />
                  <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: r.resolved ? colors.ink2 : colors.danger }}>
                    {r.name}
                  </Text>
                  <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>
                    {r.kind}
                  </Text>
                </View>
              ))}
            </View>
          ) : null}

          {files.length > 0 ? (
            <View style={{ gap: space.s2 }}>
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3, letterSpacing: 0.6 }}>
                FILES · {files.length}
              </Text>
              {files.map((f) => (
                <View key={f.path} style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
                  <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3 }} numberOfLines={1}>
                    {f.path}
                  </Text>
                  {f.kind === 'locked-dir' ? (
                    <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>
                      locked · {f.count} {f.mode ? `· ${f.mode}` : ''}
                    </Text>
                  ) : null}
                </View>
              ))}
            </View>
          ) : null}

          <Text
            style={{
              fontFamily: fonts.mono,
              fontSize: fontSizes.sm,
              lineHeight: fontSizes.sm * 1.55,
              color: colors.ink,
            }}
          >
            {detail.body || '(empty)'}
          </Text>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

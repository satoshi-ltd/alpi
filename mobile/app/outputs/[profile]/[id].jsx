import * as Clipboard from 'expo-clipboard';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useMemo } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Diamond } from '../../../src/components/Diamond';
import { NotificationBody } from '../../../src/components/NotificationBody';
import { ScreenHeader } from '../../../src/components/ScreenHeader';
import { useToast } from '../../../src/components/Toast';
import { useProfileSummaries } from '../../../src/hooks/useDaemonData';
import { useOutput } from '../../../src/hooks/useOutputs';
import { openChatTarget, severityTag } from '../../../src/lib/outputsFormat';
import { accentForProfile } from '../../../src/theme/accents';
import { useTheme } from '../../../src/theme/ThemeContext';
import { radii, space } from '../../../src/theme/tokens';


function fmtRelative(ts) {
  if (!ts) return '';
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return 'now';
  if (diff < 3600) return `${Math.round(diff / 60)}m`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h`;
  if (diff < 86400 * 7) return `${Math.round(diff / 86400)}d`;
  return `${Math.round(diff / (86400 * 7))}w`;
}


function PillButton({ label, trailing, onPress }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s2,
        paddingHorizontal: space.s4,
        paddingVertical: space.s3,
        borderRadius: radii.md,
        backgroundColor: pressed ? colors.selected : colors.hover,
      })}
    >
      <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.ink }}>
        {label}
      </Text>
      {trailing ? (
        <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.ink3 }}>
          {trailing}
        </Text>
      ) : null}
    </Pressable>
  );
}


export default function OutputDetailScreen() {
  const { colors, fonts, fontSizes } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const { profile, id, connectionId } = useLocalSearchParams();
  const { row, loading, error, markRead } = useOutput(profile, id, connectionId);
  const summaries = useProfileSummaries();

  useEffect(() => {
    if (row && row.status === 'unread') markRead();
  }, [row, markRead]);

  const accent = useMemo(() => {
    if (!row) return colors.ink3;
    const fromDaemon = (summaries.data?.profiles ?? []).find((p) => p.name === row.profile);
    return fromDaemon?.accent ?? accentForProfile(row.profile);
  }, [row, summaries.data, colors.ink3]);

  const onCopy = async () => {
    if (!row) return;
    try {
      await Clipboard.setStringAsync(String(row.body ?? ''));
      toast({ title: 'Copied' });
    } catch (e) {
      toast({ title: 'Copy failed', kind: 'danger' });
    }
  };

  const chatTarget = openChatTarget(row, connectionId);
  const sev = row ? severityTag(row) : null;

  const subtitleNode = row ? (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
      <Diamond color={accent} />
      <Text
        style={{
          fontFamily: fonts.mono,
          fontSize: fontSizes.xs,
          lineHeight: space.s6,
          color: colors.ink3,
        }}
      >
        @{row.profile} · {fmtRelative(row.created_at)} ago
      </Text>
    </View>
  ) : null;

  const rowTitle = (row?.title || '').trim();
  const headerTitle = rowTitle || 'Notification';

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title={headerTitle}
        subtitle={subtitleNode}
        onBack={() => router.back()}
      />

      {loading && !row ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.ink3} />
        </View>
      ) : error || !row ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s10, gap: space.s2 }}>
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink2 }}>
            Notification not found
          </Text>
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3, textAlign: 'center' }}>
            It may have aged out of the 500-row cap on this profile.
          </Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: space.s7, gap: space.s5, paddingBottom: space.s10 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2, flexWrap: 'wrap' }}>
            {sev ? (
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: sev === 'WARNING' ? colors.warning : colors.danger, letterSpacing: 0.6 }}>
                {sev}
              </Text>
            ) : null}
          </View>

          <NotificationBody body={row.body || ''} lead={!rowTitle} />

          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              gap: space.s3,
              paddingTop: space.s5,
              borderTopWidth: 0.5,
              borderTopColor: colors.line,
            }}
          >
            {chatTarget ? (
              <PillButton label="Open chat" trailing="→" onPress={() => router.push(chatTarget)} />
            ) : null}
            <PillButton label="Copy" onPress={onCopy} />
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

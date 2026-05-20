import { useRouter } from 'expo-router';
import { useMemo } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { radii, space , fontSizes} from '../../theme/tokens';

import { Glyph } from '../../components/Glyph';
import { Sheet } from '../../components/Sheet';
import { Row, SectionHeader } from '../../components/Row';
import { useActivityLog } from '../../hooks/useActivityLog';
import { useProfileSummaries, useWorkgroups } from '../../hooks/useDaemonData';
import { accentForProfile } from '../../theme/accents';
import { useTheme } from '../../theme/ThemeContext';

const KIND_PHRASE = {
  'wg.post': 'new message',
  'wg.task': 'new #task',
  'wg.done': '#done',
  'wg.skip': '#skip',
  'schedule.done': 'schedule fired',
  'schedule.failed': 'schedule failed',
  'budget.threshold': 'budget warning',
  'mention': '@mention',
  'peer.pairing_request': 'wants to pair',
  'daemon.offline': 'daemon offline',
};

function eventSubject(ev) {
  const d = ev.data ?? {};
  if (d.wg_id) return { kind: 'workgroup', id: d.wg_id, profile: d.profile };
  if (d.profile) return { kind: 'profile', id: d.profile };
  return { kind: 'system', id: ev.event };
}

function rowName(ev, subject) {
  const phrase = KIND_PHRASE[ev.event] ?? ev.event;
  if (subject.kind === 'workgroup') return `${subject.id} · ${phrase}`;
  if (subject.kind === 'profile') return `${subject.id} · ${phrase}`;
  return phrase;
}

function eventPreview(ev) {
  const d = ev.data ?? {};
  if (ev.event === 'wg.post' || ev.event === 'wg.done') {
    const body = d.body?.split('\n')[0]?.trim();
    return body || KIND_PHRASE[ev.event] || ev.event;
  }
  if (ev.event === 'session_changed') {
    return d.preview || d.first_user || KIND_PHRASE[ev.event];
  }
  if (ev.event === 'schedule.done' || ev.event === 'schedule.failed') {
    return d.job_id ? `${KIND_PHRASE[ev.event]} · ${d.job_id}` : KIND_PHRASE[ev.event];
  }
  if (ev.event === 'budget.threshold') {
    const pct = typeof d.threshold === 'number' ? `${Math.round(d.threshold * 100)}%` : '';
    return `Budget ${pct} reached`.trim();
  }
  return KIND_PHRASE[ev.event] ?? ev.event;
}

function dayKey(ts) {
  if (!ts) return 'older';
  const d = new Date(ts * 1000);
  const today = new Date();
  const sameDay = (a, b) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  if (sameDay(d, today)) return 'today';
  const yest = new Date(today);
  yest.setDate(today.getDate() - 1);
  if (sameDay(d, yest)) return 'yesterday';
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

function dayLabel(key) {
  if (key === 'today') return 'Today';
  if (key === 'yesterday') return 'Yesterday';
  return key;
}

function fmtRel(ts) {
  if (!ts) return '';
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return 'now';
  if (diff < 3600) return `${Math.round(diff / 60)}m`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h`;
  if (diff < 86400 * 7) return `${Math.round(diff / 86400)}d`;
  return `${Math.round(diff / (86400 * 7))}w`;
}

export function ActivitySheet({ open, onClose }) {
  const { colors, fonts , fontSizes} = useTheme();
  const router = useRouter();
  const { history, loading } = useActivityLog();
  const summaries = useProfileSummaries();
  const wgs = useWorkgroups();
  // wg_id → hub_id lookup so workgroup rows can borrow the hub profile's accent (wg has no own accent).
  const wgHubByWgId = useMemo(() => {
    const m = new Map();
    for (const w of (wgs.data?.workgroups ?? [])) m.set(w.id, w.hub_id);
    return m;
  }, [wgs.data]);
  const profileAccentByName = useMemo(() => {
    const m = new Map();
    for (const p of (summaries.data?.profiles ?? [])) m.set(p.name, p.accent);
    return m;
  }, [summaries.data]);

  const grouped = useMemo(() => {
    const byDay = new Map();
    // Drop any control frame that slipped past useEvents (defense-in-depth).
    const ordered = [...history]
      .filter((ev) => ev.event && ev.event !== 'subscribed')
      .sort((a, b) => (b.at ?? 0) - (a.at ?? 0));
    for (const ev of ordered) {
      const key = dayKey(ev.at);
      if (!byDay.has(key)) byDay.set(key, []);
      byDay.get(key).push(ev);
    }
    return Array.from(byDay.entries());
  }, [history]);

  const handleOpen = (subject) => {
    onClose?.();
    if (subject.kind === 'profile') router.push(`/chat/${subject.id}`);
    else if (subject.kind === 'workgroup') router.push(`/wg/${subject.id}`);
  };

  return (
    <Sheet open={open} onClose={onClose} title="Activity" subtitle="EVENTS LOG">
      <ScrollView contentContainerStyle={{ paddingBottom: space.s9 }}>
        {loading && history.length === 0 ? (
          <View style={{ padding: space.s10, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        ) : history.length === 0 ? (
          <View style={{ padding: space.s10, alignItems: 'center', gap: space.s2 }}>
            <Text style={{ fontFamily: fonts.sans.medium, color: colors.ink2, fontSize: fontSizes.lg }}>
              Nothing here yet.
            </Text>
            <Text
              style={{
                fontFamily: fonts.sans.regular,
                color: colors.ink3,
                fontSize: fontSizes.md,
                textAlign: 'center',
              }}
            >
              Activity fires as your daemons post, schedule jobs, or cross budget thresholds.
            </Text>
          </View>
        ) : (
          grouped.map(([day, items]) => (
            <View key={day}>
              <SectionHeader>{dayLabel(day)}</SectionHeader>
              {items.map((ev, i) => {
                const subject = eventSubject(ev);
                let accent;
                if (subject.kind === 'profile') {
                  accent = profileAccentByName.get(subject.id) ?? accentForProfile(subject.id);
                } else if (subject.kind === 'workgroup') {
                  const hubName = wgHubByWgId.get(subject.id);
                  accent = (hubName && profileAccentByName.get(hubName)) ?? accentForProfile(hubName);
                } else {
                  accent = colors.warning;
                }
                const label = rowName(ev, subject);
                return (
                  <Pressable key={`${day}-${i}`} onPress={() => handleOpen(subject)}>
                    <Row
                      leading={
                        subject.kind === 'system' ? (
                          <View
                            style={{
                              width: 36,
                              height: 36,
                              borderRadius: radii.xl,
                              backgroundColor: `${colors.warning}22`,
                              alignItems: 'center',
                              justifyContent: 'center',
                            }}
                          >
                            <Text style={{ color: colors.warning, fontSize: fontSizes.msg }}>!</Text>
                          </View>
                        ) : (
                          <Glyph
                            kind={subject.kind === 'workgroup' ? 'workgroup' : 'profile'}
                            color={accent}
                            size={36}
                          />
                        )
                      }
                      label={label}
                      helper={eventPreview(ev)}
                      value={
                        <Text
                          style={{
                            fontFamily: fonts.monoMedium,
                            fontSize: fontSizes.xs,
                            color: colors.ink3,
                          }}
                        >
                          {fmtRel(ev.at)}
                        </Text>
                      }
                      chevron={false}
                    />
                  </Pressable>
                );
              })}
            </View>
          ))
        )}
      </ScrollView>
    </Sheet>
  );
}

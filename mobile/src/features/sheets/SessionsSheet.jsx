import { useMemo } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { space } from '../../theme/tokens';

import { PickerRow } from '../../components/PickerRow';
import { Row, RowSeparator, SectionHeader } from '../../components/Row';
import { Sheet } from '../../components/Sheet';
import { useSessionsList } from '../../hooks/useDaemonData';
import { useTheme } from '../../theme/ThemeContext';
import { SessionsSkeleton } from './SessionsSkeleton';

const DAY_MS = 86400000;

function startOfDay(ms) {
  const d = new Date(ms);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function bucketFor(ms) {
  const today = startOfDay(Date.now());
  if (ms >= today) return 'Today';
  if (ms >= today - DAY_MS) return 'Yesterday';
  if (ms >= today - 7 * DAY_MS) return 'This week';
  return 'Earlier';
}

const BUCKET_ORDER = ['Today', 'Yesterday', 'This week', 'Earlier'];

function previewOf(s) {
  const t = (s.first_user || '').trim();
  if (t) return t.length > 64 ? `${t.slice(0, 64)}…` : t;
  return `(empty · ${(s.id || '').slice(0, 6)})`;
}

function fmtCost(n) {
  if (n == null || n <= 0) return null;
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}

export function SessionsSheet({ open, onClose, profile, accent, activeSessionId, onPick, onNew }) {
  const { colors, fonts, fontSizes } = useTheme();
  const sessions = useSessionsList(profile, 30, { skipWhen: !open });
  const rows = useMemo(
    () => (sessions.data?.sessions ?? []).filter((s) => (s.kind ?? 'chat') === 'chat'),
    [sessions.data],
  );

  const groups = useMemo(() => {
    const m = new Map();
    for (const s of rows) {
      const ts = (s.updated_at ?? s.started_at ?? s.mtime ?? 0) * 1000;
      const k = bucketFor(ts);
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(s);
    }
    return m;
  }, [rows]);

  const buckets = BUCKET_ORDER.filter((b) => groups.has(b));

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Sessions"
      subtitle={`@${profile ?? ''} · ${rows.length} sessions`}
      primaryAction={{
        label: '+ New session',
        onPress: () => {
          onNew?.();
          onClose?.();
        },
      }}
    >
      <ScrollView contentContainerStyle={{ paddingBottom: space.s7 }}>
        {sessions.loading && rows.length === 0 ? (
          <SessionsSkeleton />
        ) : rows.length === 0 ? (
          <Row label="No previous sessions" helper="start one to fill the list" chevron={false} />
        ) : (
          buckets.map((b) => (
            <View key={b}>
              <SectionHeader>{b}</SectionHeader>
              {groups.get(b).map((s, i) => {
                const cost = fmtCost(s.cost_usd);
                const helper = (
                  <View style={{ flexDirection: 'row', gap: space.s3, alignItems: 'center' }}>
                    <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>
                      {s.turn_count} turn{s.turn_count === 1 ? '' : 's'}
                    </Text>
                    {cost ? (
                      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>
                        · {cost}
                      </Text>
                    ) : null}
                  </View>
                );
                return (
                  <View key={s.id}>
                    {i > 0 ? <RowSeparator /> : null}
                    <PickerRow
                      selected={s.id === activeSessionId}
                      accent={accent}
                      label={previewOf(s)}
                      helper={helper}
                      onPress={() => {
                        onPick?.(s.id);
                        onClose?.();
                      }}
                    />
                  </View>
                );
              })}
            </View>
          ))
        )}
      </ScrollView>
    </Sheet>
  );
}

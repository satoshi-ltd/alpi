import { useFocusEffect, usePathname, useRouter } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { SectionList, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { WORKGROUP_FILTERS, filterCounts, noMatchLine, workgroupSummaryLine } from '../../common/workgroupList.mjs';
import { Busy } from '../src/components/Busy';
import { Eyebrow } from '../src/components/Eyebrow';
import { Icon } from '../src/components/Icon';
import { LoadFailed } from '../src/components/LoadFailed';
import { ScreenHeader } from '../src/components/ScreenHeader';
import { Segmented } from '../src/components/Segmented';
import { useWell } from '../src/components/well';
import { InboxRow } from '../src/features/inbox/InboxRow';
import { rowStateFor, useActivity } from '../src/hooks/useActivity';
import { useBack } from '../src/hooks/useBack';
import { useInbox } from '../src/hooks/useInbox';
import { usePullRefresh } from '../src/hooks/usePullRefresh';
import { openVerb, SETTINGS_COLUMN_MAX_W, subjectPath } from '../src/lib/panes';
import { withActivity, workgroupSections } from '../src/lib/roster';
import { isDaemonDown } from '../src/components/DaemonBanner';
import { useEndpoint } from '../src/lib/EndpointContext';
import { usePane } from '../src/nav/PaneContext';
import { useTheme } from '../src/theme/ThemeContext';
import { space } from '../src/theme/tokens';

function SearchField({ query, onChange }) {
  const { colors, fonts, fontSizes, mobile } = useTheme();
  const [well, focus] = useWell(colors);
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3, marginHorizontal: space.s7, marginBottom: space.s3, paddingHorizontal: space.s5, height: mobile.inputH, ...well }}>
      <Icon name="search" size="md" color={colors.ink3} />
      <TextInput
        value={query}
        onChangeText={onChange}
        {...focus}
        autoCapitalize="none"
        autoCorrect={false}
        accessibilityLabel="Search workgroups"
        placeholder="Search workgroups"
        placeholderTextColor={colors.ink3}
        style={{ flex: 1, fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink }}
      />
    </View>
  );
}

export default function WorkgroupsScreen() {
  const { colors, fonts, fontSizes } = useTheme();
  const router = useRouter();
  const pathname = usePathname();
  const goBack = useBack();
  const { twoPane } = usePane();
  const { items, loading, refresh, error } = useInbox();
  const activity = useActivity();
  const { endpoint, probeState } = useEndpoint();
  const offline = !!endpoint && isDaemonDown(probeState.get(endpoint.id) ?? 'unknown');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');

  useFocusEffect(useCallback(() => { refresh(); }, [refresh]));
  const pull = usePullRefresh(useCallback(async () => { await Promise.all([refresh(), activity.refresh()]); }, [refresh, activity.refresh]));

  const workgroups = useMemo(
    () => items.filter((item) => item.kind === 'workgroup').map((item) => withActivity(item, rowStateFor(activity.states, item))),
    [items, activity.states],
  );
  const counts = useMemo(() => filterCounts(workgroups.map((item) => item.stateId)), [workgroups]);
  const summary = useMemo(() => workgroupSummaryLine(workgroups.map((item) => item.stateId)), [workgroups]);
  const sections = useMemo(() => workgroupSections(workgroups, filter, query), [workgroups, filter, query]);
  const options = WORKGROUP_FILTERS.map((item) => ({
    value: item.id,
    label: `${item.label} ${counts[item.id]}`,
    spoken: `${item.label}, ${counts[item.id]}`,
    disabled: counts[item.id] === 0,
  }));

  const openItem = useCallback((item) => router[openVerb({ twoPane, pathname })](subjectPath(item)), [router, twoPane, pathname]);
  const renderItem = useCallback(({ item }) => <InboxRow item={item} onPress={openItem} offline={offline} full />, [openItem, offline]);
  const renderSectionHeader = useCallback(
    ({ section }) => (section.label ? (
      <View style={{ paddingHorizontal: space.s7, paddingTop: space.s5, paddingBottom: space.s2 }}>
        <Eyebrow color={section.key === 'needs' ? colors.warningText : undefined}>{`${section.label} · ${section.data.length}`}</Eyebrow>
      </View>
    ) : null),
    [colors],
  );

  const column = twoPane ? { maxWidth: SETTINGS_COLUMN_MAX_W, width: '100%', alignSelf: 'center' } : null;
  const empty = loading && workgroups.length === 0
    ? <Busy size={18} label="Reaching the daemon" style={{ padding: space.s9, justifyContent: 'center' }} />
    : <Text style={{ padding: space.s9, textAlign: 'center', fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3 }}>{noMatchLine(filter, query)}</Text>;

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader title="Workgroups" subtitle={summary} onBack={goBack} />
      {error && workgroups.length === 0 ? (
        <LoadFailed label="workgroups" error={error} onRetry={refresh} />
      ) : (
        <View style={[{ flex: 1 }, column]}>
          <SearchField query={query} onChange={setQuery} />
          <View style={{ paddingHorizontal: space.s7, paddingBottom: space.s2 }}>
            <Segmented label="Filter workgroups" options={options} value={filter} onChange={setFilter} />
          </View>
          <SectionList
            style={{ flex: 1 }}
            sections={sections}
            keyExtractor={(item) => `${item.profile}/${item.id}`}
            renderItem={renderItem}
            renderSectionHeader={renderSectionHeader}
            stickySectionHeadersEnabled={false}
            keyboardShouldPersistTaps="handled"
            refreshing={pull.refreshing}
            onRefresh={pull.onRefresh}
            contentContainerStyle={{ paddingBottom: space.s10, flexGrow: 1 }}
            ListEmptyComponent={empty}
          />
        </View>
      )}
    </SafeAreaView>
  );
}

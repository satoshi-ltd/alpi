import { useCallback, useMemo } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, SectionList, Text, TextInput, View } from 'react-native';
import { radii, space } from '../../theme/tokens';

import { Eyebrow } from '../../components/Eyebrow';
import { Icon } from '../../components/Icon';
import { rosterIsEmpty, rosterSections } from '../../lib/roster';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { SEPARATOR_INSET } from './InboxRow';
import { InboxSkeleton } from './InboxSkeleton';

const HAIRLINE = 0.5;
const EMPTY_MIN_H = 240;
const CONTENT_PAD_BOTTOM = space.s9;

function rosterKey(item) {
  return `${item.kind}:${item.kind === 'workgroup' ? `${item.profile}/` : ''}${item.id}`;
}

function SearchField({ query, onQueryChange, gutter }) {
  const { colors, fonts, fontSizes, mobile } = useTheme();
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s3,
        marginHorizontal: gutter,
        marginBottom: space.s3,
        paddingHorizontal: space.s5,
        height: mobile.inputH,
        backgroundColor: colors.bgElev,
        borderRadius: radii.xl,
        borderWidth: HAIRLINE,
        borderColor: colors.line,
      }}
    >
      <Icon name="search" size="md" color={colors.ink3} />
      <TextInput
        value={query}
        onChangeText={onQueryChange}
        autoFocus
        autoCapitalize="none"
        autoCorrect={false}
        accessibilityLabel="Filter list"
        placeholder="Filter profiles & workgroups"
        placeholderTextColor={colors.ink4}
        style={{ flex: 1, fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink }}
      />
    </View>
  );
}

function SectionAdd({ label, onPress }) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      hitSlop={{ top: space.s7, bottom: space.s3, left: space.s7, right: space.s7 }}
      accessibilityLabel={label}
    >
      <Icon name="plus" size="sm" color={colors.ink3} />
    </Pressable>
  );
}

function EmptyState({ paired, query, device }) {
  const { colors, fonts, fontSizes } = useTheme();
  const needle = String(query ?? '').trim();
  const [title, body] = !paired
    ? ['Not paired', `Pair this ${device} to a daemon and its profiles show up here.`]
    : needle
      ? ['No matches', `Nothing matches “${needle}”.`]
      : ['Nothing here yet', 'This daemon has no profiles or workgroups yet.'];
  return (
    <View
      style={{
        flex: 1,
        alignItems: 'center',
        justifyContent: 'center',
        padding: space.s8,
        gap: space.s3,
        minHeight: EMPTY_MIN_H,
      }}
    >
      <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink2, textAlign: 'center' }}>
        {title}
      </Text>
      <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3, textAlign: 'center' }}>
        {body}
      </Text>
    </View>
  );
}

export function Roster({
  items = [],
  query = '',
  onQueryChange,
  renderRow,
  loading = false,
  refreshing = false,
  onRefresh,
  paired = true,
  device = 'device',
  gutter = space.s7,
  addActions = null,
  searchOpen = false,
}) {
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const keepEmpty = useMemo(() => Object.keys(addActions ?? {}), [addActions]);
  const sections = useMemo(() => rosterSections(items, query, { keepEmpty }), [items, query, keepEmpty]);
  const empty = rosterIsEmpty(sections);
  const placeholder = loading ? <InboxSkeleton /> : <EmptyState paired={paired} query={query} device={device} />;

  const renderSectionHeader = useCallback(
    ({ section }) => {
      const add = section.key === 'pinned' ? null : addActions?.[section.key];
      return (
        <View
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            gap: space.s3,
            paddingHorizontal: gutter,
            paddingTop: space.s5,
            paddingBottom: space.s2,
          }}
        >
          <Eyebrow style={{ flex: 1 }}>{section.label}</Eyebrow>
          {add ? <SectionAdd label={add.label} onPress={add.onPress} /> : null}
        </View>
      );
    },
    [fonts, fontSizes, colors, gutter, addActions],
  );

  const separator = useCallback(
    () => <View style={{ height: HAIRLINE, backgroundColor: colors.line, marginLeft: SEPARATOR_INSET }} />,
    [colors.line],
  );

  return (
    <View style={{ flex: 1 }}>
      {searchOpen ? (
        <SearchField query={query} onQueryChange={onQueryChange} gutter={gutter} />
      ) : null}
      <SectionList
        style={{ flex: 1 }}
        sections={sections}
        keyExtractor={rosterKey}
        renderItem={renderRow}
        renderSectionHeader={renderSectionHeader}
        stickySectionHeadersEnabled={false}
        keyboardShouldPersistTaps="handled"
        ItemSeparatorComponent={twoPane ? undefined : separator}
        contentContainerStyle={{ paddingBottom: CONTENT_PAD_BOTTOM, flexGrow: 1 }}
        refreshControl={
          onRefresh ? (
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink3} />
          ) : undefined
        }
        ListEmptyComponent={placeholder}
        ListFooterComponent={
          sections.length === 0 ? null : empty ? (
            placeholder
          ) : loading ? (
            <View style={{ padding: space.s9, alignItems: 'center' }}>
              <ActivityIndicator color={colors.ink3} />
            </View>
          ) : null
        }
      />
    </View>
  );
}

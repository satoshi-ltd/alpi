import { useCallback, useMemo } from 'react';
import { Pressable, RefreshControl, SectionList, Text, TextInput, View } from 'react-native';
import { mobile, radii, space } from '../../theme/tokens';
import { TWIN_SHAPE } from '../../../../common/shapes.mjs';
import { MARK_SIZES } from '../../../../common/agentMarks.mjs';

import { Button } from '../../components/Button';
import { EmptyState } from '../../components/EmptyState';
import { Eyebrow } from '../../components/Eyebrow';
import { Fold } from '../../components/Fold';
import { Icon } from '../../components/Icon';
import { firstRun, firstRunType, foldMarkStyle } from '../../lib/firstRun';
import { isFirstProfile, rosterIsEmpty, rosterSections, TILES_KEY, tileSections, useSettledOnce } from '../../lib/roster';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { InboxSkeleton } from './InboxSkeleton';
import { memberEmptyCopy, pairedRoleLine } from '../../../../common/onboarding.mjs';
import { EMPTY } from '../../../../common/emptyCopy.mjs';
import { plainError } from '../../../../common/plainError.mjs';
import { useWell } from '../../components/well';
import { Busy } from '../../components/Busy';

const CONTENT_PAD_BOTTOM = space.s9;

function rosterKey(item) {
  if (item.kind === TILES_KEY) return TILES_KEY;
  return `${item.kind}:${item.kind === 'workgroup' ? `${item.profile}/` : ''}${item.id}`;
}

function SearchField({ query, onQueryChange, gutter }) {
  const { colors, fonts, fontSizes, mobile } = useTheme();
  const [well, focus] = useWell(colors);
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
        ...well,
      }}
    >
      <Icon name="search" size="md" color={colors.ink3} />
      <TextInput
        value={query}
        onChangeText={onQueryChange}
        {...focus}
        autoFocus
        autoCapitalize="none"
        autoCorrect={false}
        accessibilityLabel="Filter list"
        placeholder="Filter profiles & workgroups"
        placeholderTextColor={colors.ink3}
        style={{ flex: 1, fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink }}
      />
    </View>
  );
}

const ADD_BOX = space.s10;
export const ADD_BLEED = (mobile.tap - ADD_BOX) / 2;

function SectionAdd({ label, onPress }) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => ({
        width: mobile.tap,
        height: mobile.tap,
        marginVertical: -space.s2 - ADD_BLEED,
        marginHorizontal: -ADD_BLEED,
        borderRadius: radii.pill,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed ? colors.pressed : 'transparent',
      })}
    >
      <Icon name="plus" size="xs" color={colors.ink3} />
    </Pressable>
  );
}

function RosterFirstRun({ device, member, onCreate }) {
  const theme = useTheme();
  const type = firstRunType(theme, theme.fontSizes.xxl);
  const copy = member ? memberEmptyCopy(device ? `this ${device}` : null) : { title: EMPTY.roster.title, hint: EMPTY.roster.hint };
  return (
    <View style={{ flex: 1, paddingTop: firstRun.top, paddingHorizontal: firstRun.edge, paddingBottom: firstRun.stack }}>
      <View style={{ flex: 1 }}>
        <View style={foldMarkStyle}>
          <Fold shape={TWIN_SHAPE} size={MARK_SIZES.hero} />
        </View>
        <Text accessibilityRole="header" style={type.title}>{copy.title}</Text>
        {member ? <Text style={type.fact}>{pairedRoleLine('member', 0)}</Text> : null}
        <Text style={type.sentence}>{copy.hint}</Text>
      </View>
      {member ? null : <Button title="New profile" size="hero" fullWidth onPress={onCreate} />}
    </View>
  );
}

function RosterEmpty({ paired, query, device, canCreate = false, daemonDown = false, error = null, onRetry, onCreate, first = false }) {
  if (first) return <RosterFirstRun device={device} member={!canCreate} onCreate={onCreate} />;
  const needle = String(query ?? '').trim();
  const [title, body] = !paired
    ? ['Not paired', `Pair this ${device} to a daemon and its profiles show up here.`]
    : needle
      ? [EMPTY.matches.title, EMPTY.matches.hint]
      : daemonDown
        ? ['Daemon unreachable', 'Profiles and workgroups show up again once the connection is back.']
        : error
          ? ['Couldn\'t load the roster', plainError(error?.message ?? error)]
          : canCreate
            ? [EMPTY.roster.title, EMPTY.roster.hint]
            : (({ title: t, hint: h }) => [t, h])(memberEmptyCopy(device ? `this ${device}` : null));
  const retry = paired && !needle && (daemonDown || error) && onRetry;
  return <EmptyState title={title} detail={body} action={retry ? { label: 'Retry', onPress: onRetry } : null} />;
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
  daemonDown = false,
  error = null,
  endpointId,
}) {
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const keepEmpty = useMemo(() => Object.keys(addActions ?? {}), [addActions]);
  const allSections = useMemo(() => rosterSections(items, query, { keepEmpty }), [items, query, keepEmpty]);
  const initialLoading = useSettledOnce(loading, endpointId);
  const first = isFirstProfile({ empty: rosterIsEmpty(allSections), initialLoading, paired, query, daemonDown, error });
  const sections = useMemo(() => (first ? [] : tileSections(allSections)), [first, allSections]);
  const empty = rosterIsEmpty(sections);
  const placeholder = initialLoading ? <InboxSkeleton label="Loading profiles and workgroups" /> : <RosterEmpty paired={paired} query={query} device={device} canCreate={addActions != null} daemonDown={daemonDown} error={error} onRetry={onRefresh} onCreate={addActions?.profiles?.onPress} first={first} />;

  const renderSectionHeader = useCallback(
    ({ section }) => {
      if (!section.label) return null;
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

  const seamAfterTiles = sections.length > 1 && sections[0].key === TILES_KEY;
  const renderSectionFooter = useCallback(
    ({ section }) =>
      section.key === TILES_KEY && seamAfterTiles ? (
        <View testID="front-seam" style={{ height: space.s3 }} />
      ) : null,
    [seamAfterTiles],
  );

  const renderItem = useCallback(
    (info) =>
      info.item.kind === TILES_KEY ? (
        <View testID="pinned-tiles" accessibilityRole="list" style={{ flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: gutter - space.s2, paddingTop: space.s1, paddingBottom: space.s2 }}>
          {info.item.items.map((item) => (
            <View key={rosterKey(item)} style={{ width: '33.3333%' }}>{renderRow({ item, tile: true })}</View>
          ))}
        </View>
      ) : (
        renderRow(info)
      ),
    [renderRow, gutter],
  );

  const pull = useCallback(() => onRefresh?.(), [onRefresh]);

  return (
    <View style={{ flex: 1 }}>
      {searchOpen ? (
        <SearchField query={query} onQueryChange={onQueryChange} gutter={gutter} />
      ) : null}
      <SectionList
        style={{ flex: 1 }}
        sections={sections}
        keyExtractor={rosterKey}
        renderItem={renderItem}
        renderSectionHeader={renderSectionHeader}
        renderSectionFooter={renderSectionFooter}
        stickySectionHeadersEnabled={false}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ paddingBottom: first ? 0 : CONTENT_PAD_BOTTOM, flexGrow: 1 }}
        refreshControl={
          onRefresh ? (
            <RefreshControl refreshing={refreshing} onRefresh={pull} tintColor={colors.ink3} />
          ) : undefined
        }
        ListEmptyComponent={placeholder}
        ListFooterComponent={
          sections.length === 0 ? null : empty ? (
            placeholder
          ) : loading ? (
            <Busy size={18} label="Refreshing profiles and workgroups" style={{ padding: space.s9, justifyContent: 'center' }} />
          ) : null
        }
      />
    </View>
  );
}

import { useCallback, useMemo } from 'react';
import { Pressable, RefreshControl, SectionList, Text, TextInput, View } from 'react-native';
import { mobile, radii, space } from '../../theme/tokens';
import { ALPACA_FOLD, FOLD_SIZES } from '../../../../common/folds.mjs';

import { Button } from '../../components/Button';
import { EmptyState } from '../../components/EmptyState';
import { Eyebrow } from '../../components/Eyebrow';
import { Fold } from '../../components/Fold';
import { Icon } from '../../components/Icon';
import { firstRun, firstRunType, foldMarkStyle } from '../../lib/firstRun';
import { isFirstProfile, rosterIsEmpty, rosterSections, useSettledOnce } from '../../lib/roster';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { SEPARATOR_INSET } from './InboxRow';
import { InboxSkeleton } from './InboxSkeleton';
import { memberEmptyCopy, pairedRoleLine } from '../../../../common/onboarding.mjs';
import { EMPTY } from '../../../../common/emptyCopy.mjs';
import { plainError } from '../../../../common/plainError.mjs';
import { useWell } from '../../components/well';
import { Busy } from '../../components/Busy';

const HAIRLINE = 0.5;
const CONTENT_PAD_BOTTOM = space.s9;

function rosterKey(item) {
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

function SectionAdd({ label, onPress }) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      hitSlop={(mobile.tap - ADD_BOX) / 2}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => ({
        width: ADD_BOX,
        height: ADD_BOX,
        marginVertical: -space.s2,
        borderRadius: radii.xs,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed ? colors.selected : 'transparent',
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
          <Fold fold={ALPACA_FOLD} size={FOLD_SIZES.hero} />
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
  const sections = first ? [] : allSections;
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

  const seamAfterFront = sections.length > 1 && sections[0].key === 'front';
  const renderSectionFooter = useCallback(
    ({ section }) =>
      section.key === 'front' && seamAfterFront ? (
        <View testID="front-seam" style={{ height: HAIRLINE, backgroundColor: colors.line2 }} />
      ) : null,
    [seamAfterFront, colors.line2],
  );

  const pull = useCallback(() => onRefresh?.(), [onRefresh]);

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
        renderSectionFooter={renderSectionFooter}
        stickySectionHeadersEnabled={false}
        keyboardShouldPersistTaps="handled"
        ItemSeparatorComponent={twoPane ? undefined : separator}
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

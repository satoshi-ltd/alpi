import { useRef, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { MARK_SIZES } from '../../../../common/agentMarks.mjs';
import { radii, space, typeLeading } from '../../theme/tokens';

import { WORKGROUP_SHAPE } from '../../../../common/shapes.mjs';
import { NAME_TEXT, nameColor, nameSize, nameStyle } from '../../theme/name';
import { Fold } from '../../components/Fold';
import { Icon } from '../../components/Icon';
import { MetaStrip } from '../../components/MetaStrip';
import { EdgeFade } from '../../components/EdgeFade';
import { useShowBack } from '../../hooks/useShowBack';
import { backMargins, CHROME_BTN, PANE_PAD_X, TOGGLE_BLEED, tapSlop } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { dotShape } from '../../components/dotShape';
import { useTheme } from '../../theme/ThemeContext';
import { ProfileDetails } from './ProfileDetails';

export const PHONE_HEADER_H = 56;
export const PHONE_SIDE_W = 88;
export const HEADER_FADE = 16;

export function headerMenuActions({
  noun = 'profile',
  paused = false,
  autoRead = false,
  onOpenSettings,
  onTogglePause,
  onToggleAutoRead,
  onOpenSkills,
  onOpenMemory,
  onOpenTools,
  onOpenSchedule,
  onRefresh,
  failedJobs = 0,
} = {}) {
  const Noun = noun.charAt(0).toUpperCase() + noun.slice(1);
  const glyph = (name) => <Icon name={name} size="md" />;
  const head = [];
  if (onOpenSettings) {
    head.push({ id: 'settings', label: `${Noun} settings`, icon: glyph('settings'), onPress: onOpenSettings });
  }
  if (onTogglePause) {
    head.push({
      id: 'pause',
      label: `${paused ? 'Resume' : 'Pause'} ${noun}`,
      icon: glyph(paused ? 'play' : 'pause'),
      onPress: onTogglePause,
    });
  }
  if (onToggleAutoRead) {
    head.push({
      id: 'auto-read',
      label: 'Auto-read replies',
      icon: glyph('volume-2'),
      kind: 'switch',
      value: autoRead,
      onValueChange: onToggleAutoRead,
    });
  }
  const brain = [];
  if (onOpenSkills) brain.push({ id: 'skills', label: 'Skills', icon: glyph('sparkle'), onPress: onOpenSkills });
  if (onOpenMemory) brain.push({ id: 'memory', label: 'Memory', icon: glyph('archive'), onPress: onOpenMemory });
  if (onOpenTools) brain.push({ id: 'tools', label: 'Tools', icon: glyph('cpu'), onPress: onOpenTools });
  if (onOpenSchedule) {
    brain.push({
      id: 'schedule',
      label: 'Schedule',
      icon: glyph('clock'),
      ...(failedJobs > 0 ? { detail: `${failedJobs} failed`, detailDanger: true, badge: true } : {}),
      onPress: onOpenSchedule,
    });
  }
  const tail = onRefresh
    ? [{ id: 'refresh', label: 'Refresh thread', icon: glyph('refresh-cw'), onPress: onRefresh }]
    : [];

  const groups = [head, brain, tail].filter((g) => g.length > 0);
  return groups.flatMap((g, i) => (i === 0 ? g : [{ divider: true }, ...g]));
}

function HeaderButton({ label, onPress, anchored = false, children }) {
  const { colors } = useTheme();
  const ref = useRef(null);
  const press = anchored
    ? () => {
        const node = ref.current;
        if (typeof node?.measureInWindow === 'function') {
          node.measureInWindow((x, y, width, height) => onPress({ x, y, width, height }));
        } else {
          onPress(null);
        }
      }
    : onPress;
  return (
    <Pressable
      ref={ref}
      onPress={press}
      hitSlop={tapSlop(CHROME_BTN)}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => ({
        width: CHROME_BTN,
        height: CHROME_BTN,
        borderRadius: radii.pill,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed ? colors.pressed : 'transparent',
      })}
    >
      {children}
    </Pressable>
  );
}

function SessionsTrigger({ onPress }) {
  const { colors } = useTheme();
  return (
    <HeaderButton label="Sessions" onPress={onPress}>
      <Icon name="history" size="md" color={colors.ink2} />
    </HeaderButton>
  );
}

function HeaderName({ kind, accent, paused, showName, title, size }) {
  const { colors, fonts, fontScale = 1 } = useTheme();
  if (showName) {
    return (
      <Text {...NAME_TEXT} style={[nameStyle(nameSize(size, fontScale), paused ? colors.ink3 : kind === 'workgroup' ? colors.ink : nameColor(accent, colors)), { flexShrink: 1 }]}>
        {title}
      </Text>
    );
  }
  return (
    <Text numberOfLines={1} style={{ flexShrink: 1, fontFamily: fonts.sans.semibold, fontSize: size, lineHeight: Math.round(size * typeLeading.title), color: colors.ink }}>
      {title}
    </Text>
  );
}

function HeaderFlag({ flag }) {
  const { colors } = useTheme();
  if (!flag) return null;
  return (
    <View
      testID="header-flag"
      accessible
      accessibilityRole="image"
      accessibilityLabel={flag.label}
      style={{ ...dotShape('md'), flexShrink: 0, backgroundColor: flag.tone === 'danger' ? colors.danger : colors.warning }}
    />
  );
}

function MetaLine({ meta }) {
  const { colors, fonts, fontSizes } = useTheme();
  if (!meta) return null;
  if (typeof meta === 'string') {
    return (
      <Text numberOfLines={1} style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, lineHeight: Math.round(fontSizes.xs * typeLeading.meta), color: colors.ink3 }}>
        {meta}
      </Text>
    );
  }
  return <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>{meta}</View>;
}

function ProfileChip({ title, open, onPress, children }) {
  const { colors } = useTheme();
  const ref = useRef(null);
  const press = () => {
    const node = ref.current;
    if (typeof node?.measureInWindow === 'function') {
      node.measureInWindow((x, y, width, height) => onPress({ x, y, width, height }));
    } else {
      onPress(null);
    }
  };
  return (
    <Pressable
      ref={ref}
      onPress={press}
      accessibilityRole="button"
      accessibilityLabel={`${title}, profile details`}
      accessibilityState={{ expanded: open }}
      style={({ pressed }) => ({
        minHeight: CHROME_BTN,
        maxWidth: '100%',
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s4,
        paddingLeft: space.s4,
        paddingRight: space.s5,
        borderRadius: radii.pill,
        backgroundColor: pressed || open ? colors.pressed : 'transparent',
      })}
    >
      {children}
      <Icon name="chevron-down" size="xs" color={colors.ink3} />
    </Pressable>
  );
}

export function ChatHeader({ kind, accent, shape, named = false, paused = false, mark = null, title, meta, details = null, flag = null, onBack, onMore, onPickSession, right, failedJobs = 0 }) {
  const { colors, fontSizes } = useTheme();
  const { twoPane, sidebarOpen, toggleSidebar } = usePane();
  const showBack = useShowBack(onBack);
  const titleSize = fontSizes.xl;
  const showName = named && typeof accent === 'string' && typeof title === 'string' && title.length > 0;
  const showSidebarToggle = twoPane && !sidebarOpen;
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [detailsAnchor, setDetailsAnchor] = useState(null);

  const markNode = <Fold shape={kind === 'profile' ? shape : WORKGROUP_SHAPE} color={accent} size={MARK_SIZES.header} seed={title} {...mark} state={paused ? 'paused' : mark?.state} />;
  const backNode = showBack ? (
    <Pressable
      onPress={onBack}
      hitSlop={tapSlop(CHROME_BTN)}
      accessibilityRole="button"
      accessibilityLabel="Back"
      style={({ pressed }) => ({
        width: CHROME_BTN,
        height: CHROME_BTN,
        borderRadius: radii.pill,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed ? colors.pressed : 'transparent',
        ...(twoPane ? backMargins(!showSidebarToggle) : {}),
      })}
    >
      <Icon name="back" size="md" color={colors.ink} />
    </Pressable>
  ) : null;
  const toggleNode = showSidebarToggle ? (
    <View style={{ marginLeft: -TOGGLE_BLEED }}>
      <HeaderButton label="Show sidebar" onPress={toggleSidebar}>
        <Icon name="panel-left" size="md" color={colors.ink2} />
      </HeaderButton>
    </View>
  ) : null;
  const actionsRow = (withRight) => (
    <View style={{ flexDirection: 'row', alignItems: 'center', flexShrink: 0 }}>
      {withRight ? right : null}
      {onPickSession ? <SessionsTrigger onPress={onPickSession} /> : null}
      {onMore ? (
        <HeaderButton anchored label={failedJobs > 0 ? `More, ${failedJobs} ${failedJobs === 1 ? 'job' : 'jobs'} failed` : 'More'} onPress={onMore}>
          <Icon name="more" size="md" color={colors.ink} />
          {failedJobs > 0 ? (
            <View
              testID="failed-jobs-dot"
              style={{ position: 'absolute', top: space.s2, right: space.s2, ...dotShape('md'), backgroundColor: colors.danger }}
            />
          ) : null}
        </HeaderButton>
      ) : null}
    </View>
  );
  const actions = actionsRow(true);

  if (!twoPane && details) {
    return (
      <View
        testID="chat-header"
        style={{ flexDirection: 'row', alignItems: 'center', minHeight: PHONE_HEADER_H, paddingHorizontal: space.s3, backgroundColor: colors.bg, zIndex: 2 }}
      >
        <View style={{ width: PHONE_SIDE_W, flexDirection: 'row', alignItems: 'center' }}>{backNode}</View>
        <View testID="header-centre" style={{ flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space.s3 }}>
          <ProfileChip
            title={title}
            open={detailsOpen}
            onPress={(anchor) => {
              setDetailsAnchor(anchor);
              setDetailsOpen(true);
            }}
          >
            {markNode}
            <HeaderName kind={kind} accent={accent} paused={paused} showName={showName} title={title} size={titleSize} />
          </ProfileChip>
          <HeaderFlag flag={flag} />
          {right}
        </View>
        <View style={{ width: PHONE_SIDE_W, flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end' }}>{actionsRow(false)}</View>
        <View pointerEvents="none" style={{ position: 'absolute', left: 0, right: 0, top: '100%', height: HEADER_FADE }}>
          <EdgeFade side="top" color={colors.bg} size={HEADER_FADE} />
        </View>
        <ProfileDetails open={detailsOpen} anchor={detailsAnchor} onClose={() => setDetailsOpen(false)} name={title} accent={accent} details={details} />
      </View>
    );
  }

  if (!twoPane) {
    return (
      <View
        testID="chat-header"
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          minHeight: PHONE_HEADER_H,
          paddingHorizontal: space.s3,
          backgroundColor: colors.bg,
          zIndex: 2,
        }}
      >
        <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center' }}>{backNode}</View>
        <View testID="header-centre" style={{ flexShrink: 1, minWidth: 0, alignItems: 'center', gap: space.s1 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3, maxWidth: '100%' }}>
            {markNode}
            <HeaderName kind={kind} accent={accent} paused={paused} showName={showName} title={title} size={titleSize} />
            <HeaderFlag flag={flag} />
          </View>
          <MetaLine meta={meta} />
        </View>
        <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end' }}>{actions}</View>
        <View pointerEvents="none" style={{ position: 'absolute', left: 0, right: 0, top: '100%', height: HEADER_FADE }}>
          <EdgeFade side="top" color={colors.bg} size={HEADER_FADE} />
        </View>
      </View>
    );
  }

  return (
    <View
      testID="chat-header"
      style={{
        flexDirection: 'row',
        alignItems: 'flex-start',
        gap: space.s4,
        paddingHorizontal: PANE_PAD_X,
        paddingTop: space.s2,
        paddingBottom: space.s3,
        backgroundColor: colors.bg,
      }}
    >
      {toggleNode}
      {backNode}
      <View style={{ flex: 1, minWidth: 0, flexDirection: 'column' }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s5 }}>
          {markNode}
          <View style={{ flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
            <HeaderName kind={kind} accent={accent} paused={paused} showName={showName} title={title} size={titleSize} />
            <HeaderFlag flag={flag} />
          </View>
          {actions}
        </View>
        {meta ? (
          typeof meta === 'string' ? (
            <MetaLine meta={meta} />
          ) : (
            <ScrollView
              horizontal
              directionalLockEnabled
              showsHorizontalScrollIndicator={false}
              style={{ flexGrow: 0 }}
              contentContainerStyle={{ flexDirection: 'row', alignItems: 'center', gap: space.s6 }}
            >
              <MetaStrip>{meta}</MetaStrip>
            </ScrollView>
          )
        ) : null}
      </View>
    </View>
  );
}

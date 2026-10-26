import { useRef } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { radii, space, lineHeights } from '../../theme/tokens';

import { WORKGROUP_FOLD } from '../../../../common/folds.mjs';
import { Crease } from '../../components/Crease';
import { Fold } from '../../components/Fold';
import { Icon } from '../../components/Icon';
import { MetaStrip } from '../../components/MetaStrip';
import { useShowBack } from '../../hooks/useShowBack';
import { backMargins, CHROME_BTN, PANE_PAD_X, TOGGLE_BLEED, tapSlop } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { dotShape } from '../../components/dotShape';
import { useTheme } from '../../theme/ThemeContext';

const CREASE_MIN_SIZE = 28;

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
        borderRadius: radii.xs,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed ? colors.selected : 'transparent',
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

export function ChatHeader({ kind, accent, fold, creased = false, paused = false, title, meta, onBack, onMore, onPickSession, right, failedJobs = 0 }) {
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane, sidebarOpen, toggleSidebar } = usePane();
  const showBack = useShowBack(onBack);
  const titleSize = fontSizes.xl;
  const showCrease = creased && typeof accent === 'string' && typeof title === 'string' && title.length > 0;
  const showSidebarToggle = twoPane && !sidebarOpen;

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'flex-start',
        gap: space.s4,
        paddingHorizontal: PANE_PAD_X,
        paddingTop: space.s2,
        paddingBottom: space.s3,
        backgroundColor: colors.bg,
        borderBottomWidth: 0.5,
        borderBottomColor: colors.line,
      }}
    >
      {showSidebarToggle ? (
        <View style={{ marginLeft: -TOGGLE_BLEED }}>
          <HeaderButton label="Show sidebar" onPress={toggleSidebar}>
            <Icon name="panel-left" size="md" color={colors.ink2} />
          </HeaderButton>
        </View>
      ) : null}
      {showBack ? (
        <Pressable
          onPress={onBack}
          hitSlop={tapSlop(CHROME_BTN)}
          accessibilityRole="button"
          accessibilityLabel="Back"
          style={{
            width: CHROME_BTN,
            height: CHROME_BTN,
            alignItems: 'center',
            justifyContent: 'center',
            ...backMargins(!showSidebarToggle),
          }}
        >
          <Icon name="back" size="md" color={colors.ink2} />
        </Pressable>
      ) : null}
      <View style={{ flex: 1, minWidth: 0, flexDirection: 'column' }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: twoPane ? space.s5 : space.s2 }}>
          <Fold fold={kind === 'profile' ? fold : WORKGROUP_FOLD} color={accent} size="md" unfolded={paused} />
          {showCrease ? (
            <Crease text={title} accent={paused ? colors.ink3 : accent} size={Math.max(CREASE_MIN_SIZE, titleSize)} style={{ flex: 1 }} />
          ) : (
            <Text
              numberOfLines={1}
              style={{
                flex: 1,
                fontFamily: fonts.sans.semibold,
                fontSize: titleSize,
                lineHeight: titleSize * lineHeights.cozy,
                color: colors.ink,
              }}
            >
              {title}
            </Text>
          )}
          <View style={{ flexDirection: 'row', alignItems: 'center', flexShrink: 0 }}>
            {right}
            {onPickSession ? <SessionsTrigger onPress={onPickSession} /> : null}
            {onMore ? (
              <HeaderButton anchored label={failedJobs > 0 ? `More, ${failedJobs} ${failedJobs === 1 ? 'job' : 'jobs'} failed` : 'More'} onPress={onMore}>
                <Icon name="more" size="md" color={colors.ink2} />
                {failedJobs > 0 ? (
                  <View
                    testID="failed-jobs-dot"
                    style={{ position: 'absolute', top: space.s2, right: space.s2, ...dotShape('md'), backgroundColor: colors.danger }}
                  />
                ) : null}
              </HeaderButton>
            ) : null}
          </View>
        </View>
        {meta ? (
          typeof meta === 'string' ? (
            <Text
              numberOfLines={1}
              style={{
                fontFamily: fonts.mono,
                fontSize: fontSizes.xs,
                lineHeight: fontSizes.xs * lineHeights.cozy,
                color: colors.ink3,
                marginTop: twoPane ? 0 : 1,
              }}
            >
              {meta}
            </Text>
          ) : (
            <ScrollView
              horizontal
              directionalLockEnabled
              showsHorizontalScrollIndicator={false}
              style={{ flexGrow: 0, marginTop: twoPane ? 0 : 1 }}
              contentContainerStyle={{
                flexDirection: 'row',
                alignItems: 'center',
                gap: twoPane ? space.s6 : space.s2,
              }}
            >
              {twoPane ? <MetaStrip>{meta}</MetaStrip> : meta}
            </ScrollView>
          )
        ) : null}
      </View>
    </View>
  );
}

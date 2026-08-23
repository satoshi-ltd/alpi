import { Pressable, ScrollView, Text, View } from 'react-native';
import { radii, space, lineHeights, tracking } from '../../theme/tokens';

import { Diamond } from '../../components/Diamond';
import { Icon } from '../../components/Icon';
import { useShowBack } from '../../hooks/useShowBack';
import { CHROME_BTN, PANE_PAD_X, tapSlop } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';

const STRIPE_H = 1.5;

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
  onOpenRuns,
  onRefresh,
} = {}) {
  const Noun = noun.charAt(0).toUpperCase() + noun.slice(1);
  const glyph = (name) => <Icon name={name} size="lg" />;
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
      detail: autoRead ? 'on' : 'off',
      onPress: onToggleAutoRead,
    });
  }
  const brain = [];
  if (onOpenSkills) brain.push({ id: 'skills', label: 'Skills', icon: glyph('sparkle'), onPress: onOpenSkills });
  if (onOpenMemory) brain.push({ id: 'memory', label: 'Memory', icon: glyph('archive'), onPress: onOpenMemory });
  if (onOpenTools) brain.push({ id: 'tools', label: 'Tools', icon: glyph('cpu'), onPress: onOpenTools });
  if (onOpenSchedule) brain.push({ id: 'schedule', label: 'Schedule', icon: glyph('clock'), onPress: onOpenSchedule });
  if (onOpenRuns) brain.push({ id: 'runs', label: 'Runs', icon: glyph('cpu'), onPress: onOpenRuns });
  const tail = onRefresh
    ? [{ id: 'refresh', label: 'Refresh thread', icon: glyph('refresh-cw'), onPress: onRefresh }]
    : [];

  const groups = [head, brain, tail].filter((g) => g.length > 0);
  return groups.flatMap((g, i) => (i === 0 ? g : [{ divider: true }, ...g]));
}

function HeaderButton({ label, onPress, children }) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      hitSlop={tapSlop(CHROME_BTN)}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => ({
        width: CHROME_BTN,
        height: CHROME_BTN,
        borderRadius: radii.md,
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
      <Icon name="clock" size="lg" color={colors.ink2} />
    </HeaderButton>
  );
}

export function ChatHeader({ kind, accent, title, meta, onBack, onMore, onPickSession, right }) {
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const showBack = useShowBack(onBack);
  const titleSize = twoPane ? fontSizes.display : fontSizes.xl;

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
            marginLeft: -space.s2,
          }}
        >
          <Icon name="back" size="lg" color={colors.ink2} />
        </Pressable>
      ) : null}
      <View style={{ flex: 1, minWidth: 0, flexDirection: 'column' }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: twoPane ? space.s5 : space.s2 }}>
          {kind === 'profile' ? (
            <Diamond color={accent} size="md" />
          ) : (
            <Text style={{ fontFamily: fonts.monoMedium, fontSize: titleSize, color: twoPane ? colors.ink4 : colors.ink3 }}>#</Text>
          )}
          <Text
            numberOfLines={1}
            style={{
              flex: 1,
              fontFamily: fonts.sans.semibold,
              fontSize: titleSize,
              lineHeight: titleSize * lineHeights.cozy,
              letterSpacing: twoPane ? titleSize * tracking.tight : 0,
              color: colors.ink,
            }}
          >
            {title}
          </Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', flexShrink: 0 }}>
            {right}
            {onPickSession ? <SessionsTrigger onPress={onPickSession} /> : null}
            {onMore ? (
              <HeaderButton label="More" onPress={onMore}>
                <Icon name="more" size="lg" color={colors.ink2} />
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
              {meta}
            </ScrollView>
          )
        ) : null}
      </View>
      <View
        style={{
          position: 'absolute',
          left: PANE_PAD_X,
          bottom: -0.5,
          height: STRIPE_H,
          width: space.s11,
          backgroundColor: accent ?? colors.accent,
        }}
      />
    </View>
  );
}

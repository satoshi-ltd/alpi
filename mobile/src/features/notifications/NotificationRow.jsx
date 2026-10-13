import { useRef } from 'react';
import { Pressable, Text, View } from 'react-native';
import ReanimatedSwipeable from 'react-native-gesture-handler/ReanimatedSwipeable';

import { FALLBACK_ACCENT } from '../../../../common/folds.mjs';
import { notificationParts } from '../../../../common/notificationParts.mjs';
import { notificationTime } from '../../../../common/notificationTime.mjs';
import { Fold } from '../../components/Fold';
import { Pill } from '../../components/Pill';
import { profileLabel } from '../../lib/profileName';
import { useReduceMotion } from '../../lib/reduceMotion';
import { useTheme } from '../../theme/ThemeContext';
import { dotSize, lineHeights, mobile, radii, space } from '../../theme/tokens';

const REDUCED = { reduceMotion: 'always' };
const ACTION_W = 76;

export function levelOf(row) {
  return row?.type === 'warning' || row?.type === 'error' ? row.type : null;
}

export function LevelPill({ row }) {
  const level = levelOf(row);
  return level ? <Pill tone={level === 'error' ? 'err' : 'warn'}>{level}</Pill> : null;
}

export function rowA11yLabel(row, { unread, multi, dayGroup = true }) {
  const { headline } = notificationParts(row);
  return [
    unread ? 'Unread' : null,
    levelOf(row),
    `@${profileLabel(row.profile)}${multi && row.connectionName ? ` on ${row.connectionName}` : ''}`,
    headline,
    notificationTime(row.created_at, { dayGroup }),
  ].filter(Boolean).join(', ');
}

function SwipeAction({ label, onPress, fg, bg }) {
  const { fonts, fontSizes } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={{ minWidth: ACTION_W, minHeight: mobile.tap, paddingHorizontal: space.s3, alignItems: 'center', justifyContent: 'center', backgroundColor: bg }}
    >
      <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.sm, color: fg, textAlign: 'center' }}>{label}</Text>
    </Pressable>
  );
}

export function NotificationRow({ row, unread, multi, dayGroup = true, selected = false, canToggleRead = true, onOpen, onToggleRead, onDelete }) {
  const { colors, fonts, fontSizes } = useTheme();
  const reduceMotion = useReduceMotion();
  const swipeRef = useRef(null);
  const accent = row.accent ?? FALLBACK_ACCENT;
  const { headline, preview } = notificationParts(row);
  const toggleLabel = unread ? 'Mark read' : 'Mark unread';
  const showToggle = unread || canToggleRead;

  const act = (fn) => () => {
    swipeRef.current?.close?.();
    fn?.(row);
  };

  const a11yActions = [
    ...(showToggle ? [{ name: 'toggleRead', label: toggleLabel }] : []),
    { name: 'delete', label: 'Delete' },
  ];
  const onAccessibilityAction = (event) => {
    const name = event?.nativeEvent?.actionName;
    if (name === 'toggleRead' && showToggle) onToggleRead?.(row);
    else if (name === 'delete') onDelete?.(row);
    else if (name === 'activate') onOpen?.(row);
  };

  const renderRightActions = () => (
    <View style={{ flexDirection: 'row' }}>
      {showToggle ? <SwipeAction label={unread ? 'Read' : 'Unread'} onPress={act(onToggleRead)} fg={colors.ink} bg={colors.selected} /> : null}
      <SwipeAction label="Delete" onPress={act(onDelete)} fg={colors.bgPane} bg={colors.ink} />
    </View>
  );

  const weight = unread ? fonts.sans.semibold : fonts.sans.regular;
  const ink = unread ? colors.ink : colors.ink2;

  return (
    <ReanimatedSwipeable
      ref={swipeRef}
      friction={2}
      rightThreshold={40}
      overshootRight={false}
      animationOptions={reduceMotion ? REDUCED : undefined}
      renderRightActions={renderRightActions}
    >
      <Pressable
        onPress={() => onOpen?.(row)}
        accessibilityRole="button"
        accessibilityState={{ selected }}
        accessibilityLabel={rowA11yLabel(row, { unread, multi, dayGroup })}
        accessibilityActions={a11yActions}
        onAccessibilityAction={onAccessibilityAction}
        style={({ pressed }) => ({
          flexDirection: 'row',
          alignItems: 'flex-start',
          gap: space.s3,
          minHeight: mobile.tap,
          paddingVertical: space.s4,
          paddingLeft: space.s4,
          paddingRight: space.s6,
          backgroundColor: pressed || selected ? colors.selected : colors.bgPane,
          borderBottomWidth: 0.5,
          borderBottomColor: colors.line,
        })}
      >
        <View style={{ width: dotSize, paddingTop: space.s3 }}>
          {unread ? <View style={{ width: dotSize, height: dotSize, borderRadius: radii.pill, backgroundColor: colors.ink }} /> : null}
        </View>
        <View style={{ paddingTop: 2 }}>
          <Fold fold={row.fold} color={accent} size={20} />
        </View>
        <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2, flexWrap: 'wrap' }}>
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: ink, flexShrink: 1 }}>
              @{profileLabel(row.profile)}
            </Text>
            {multi && row.connectionName ? (
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3, flexShrink: 1 }}>
                · {row.connectionName}
              </Text>
            ) : null}
            <View style={{ flex: 1 }} />
            <LevelPill row={row} />
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
              {notificationTime(row.created_at, { dayGroup })}
            </Text>
          </View>
          <Text style={{ fontFamily: weight, fontSize: fontSizes.lg, color: ink }} numberOfLines={1}>
            {headline}
          </Text>
          {preview ? (
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * lineHeights.cozy, color: colors.ink3 }} numberOfLines={2}>
              {preview}
            </Text>
          ) : null}
        </View>
      </Pressable>
    </ReanimatedSwipeable>
  );
}

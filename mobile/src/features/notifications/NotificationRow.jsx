import { useRef } from 'react';
import { Pressable, Text, View } from 'react-native';
import ReanimatedSwipeable from 'react-native-gesture-handler/ReanimatedSwipeable';

import { FALLBACK_ACCENT } from '../../../../common/folds.mjs';
import { headlineParts } from '../../../../common/notificationHeadline.mjs';
import { Fold } from '../../components/Fold';
import { fmtRelative, severityTag } from '../../lib/outputsFormat';
import { useReduceMotion } from '../../lib/reduceMotion';
import { useTheme } from '../../theme/ThemeContext';
import { dotSize, mobile, radii, space } from '../../theme/tokens';
import { SeverityTag } from './SeverityTag';

const REDUCED = { reduceMotion: 'always' };
const ACTION_W = 76;

export function rowA11yLabel(row, { unread, multi }) {
  const { title } = headlineParts(row);
  const sev = severityTag(row);
  return [
    unread ? 'Unread' : null,
    sev ? sev.toLowerCase() : null,
    `@${row.profile}${multi && row.connectionName ? ` on ${row.connectionName}` : ''}`,
    title,
    fmtRelative(row.created_at),
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

export function NotificationRow({ row, unread, multi, canToggleRead = true, onOpen, onToggleRead, onDelete }) {
  const { colors, fonts, fontSizes } = useTheme();
  const reduceMotion = useReduceMotion();
  const swipeRef = useRef(null);
  const accent = row.accent ?? FALLBACK_ACCENT;
  const { title, preview } = headlineParts(row);
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
        accessibilityLabel={rowA11yLabel(row, { unread, multi })}
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
          backgroundColor: pressed ? colors.selected : colors.bgPane,
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
              @{row.profile}
            </Text>
            {multi && row.connectionName ? (
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3, flexShrink: 1 }}>
                {row.connectionName}
              </Text>
            ) : null}
            <View style={{ flex: 1 }} />
            <SeverityTag row={row} />
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
              {fmtRelative(row.created_at)}
            </Text>
          </View>
          <Text style={{ fontFamily: weight, fontSize: fontSizes.lg, color: ink }} numberOfLines={2}>
            {title}
          </Text>
          {preview ? (
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }} numberOfLines={1}>
              {preview}
            </Text>
          ) : null}
        </View>
      </Pressable>
    </ReanimatedSwipeable>
  );
}

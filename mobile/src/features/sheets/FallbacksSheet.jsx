import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { radii, space } from '../../theme/tokens';

import { Icon } from '../../components/Icon';
import { PickerRow } from '../../components/PickerRow';
import { RowSeparator } from '../../components/Row';
import { Sheet } from '../../components/Sheet';
import { useToast } from '../../components/Toast';
import { modelLabel } from '../../lib/modelLabel';
import { useTheme } from '../../theme/ThemeContext';
import { FALLBACK_HINT, MAX_FALLBACKS, moveFallback, removeFallback } from '../../../../common/fallbackModels.mjs';

const TARGET = 44;

function ActionIcon({ name, label, disabled, onPress }) {
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => ({
        width: TARGET,
        height: TARGET,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: radii.xs,
        opacity: disabled ? 0.35 : 1,
        backgroundColor: pressed ? colors.selected : 'transparent',
      })}
    >
      <Icon name={name} color={colors.ink2} />
    </Pressable>
  );
}

export function FallbacksSheet({ open, onClose, profileName, list, onSave, onAdd, canAdd = true }) {
  const { colors, fonts, fontSizes } = useTheme();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const save = async (next) => {
    if (saving || next === list) return;
    setSaving(true);
    try {
      await onSave?.(next);
    } catch (e) {
      toast({ title: 'Save failed', message: String(e) });
    } finally {
      setSaving(false);
    }
  };
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Fallbacks"
      subtitle={`@${profileName ?? ''} · ${FALLBACK_HINT.replace(/\.$/, '').toLowerCase()}`}
      primaryAction={{ label: 'Done', onPress: onClose, loading: saving }}
    >
      <View style={{ paddingVertical: space.s5 }}>
        {list.length === 0 ? (
          <Text
            style={{
              paddingHorizontal: space.s7,
              paddingVertical: space.s6,
              fontFamily: fonts.sans.regular,
              fontSize: fontSizes.sm,
              color: colors.ink3,
            }}
          >
            No fallbacks: a provider outage stops the agent.
          </Text>
        ) : null}
        {list.map((model, i) => {
          const name = modelLabel(model);
          return (
            <View key={model}>
              {i > 0 ? <RowSeparator /> : null}
              <View
                style={{ flexDirection: 'row', alignItems: 'center', paddingLeft: space.s7, paddingRight: space.s3, minHeight: TARGET }}
              >
                <View style={{ flex: 1, minWidth: 0, gap: space.s1 }}>
                  <Text numberOfLines={1} style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.ink }}>
                    {`${i + 1} · ${name}`}
                  </Text>
                  <Text numberOfLines={1} style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
                    {model}
                  </Text>
                </View>
                <ActionIcon name="chevron-up" label={`Move ${name} up`} disabled={saving || i === 0} onPress={() => save(moveFallback(list, i, -1))} />
                <ActionIcon name="chevron-down" label={`Move ${name} down`} disabled={saving || i === list.length - 1} onPress={() => save(moveFallback(list, i, 1))} />
                <ActionIcon name="x" label={`Remove ${name}`} disabled={saving} onPress={() => save(removeFallback(list, i))} />
              </View>
            </View>
          );
        })}
        {list.length >= MAX_FALLBACKS ? (
          <Text style={{ paddingHorizontal: space.s7, paddingVertical: space.s6, fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>
            {`${MAX_FALLBACKS} is the most a profile can list.`}
          </Text>
        ) : canAdd ? (
          <>
            <RowSeparator />
            <PickerRow label="Add model…" helper="any model of this profile except the main one" onPress={saving ? undefined : onAdd} />
          </>
        ) : null}
      </View>
    </Sheet>
  );
}

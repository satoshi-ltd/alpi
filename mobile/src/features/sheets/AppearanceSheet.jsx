import { useEffect, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { ACCENTS, pairName, selectedAccent } from '../../../../common/accents.mjs';
import { DEFAULT_FOLD, FOLD_IDS, normaliseFold } from '../../../../common/folds.mjs';
import { radii, space } from '../../theme/tokens';

import { Eyebrow } from '../../components/Eyebrow';
import { Field } from '../../components/Field';
import { Fold } from '../../components/Fold';
import { Sheet } from '../../components/Sheet';
import { useToast } from '../../components/Toast';
import { useTheme } from '../../theme/ThemeContext';

const HEX = /^#[0-9a-f]{6}$/i;

export function AppearanceSheet({ open, onClose, profileName, initialValue, initialFold, onSave }) {
  const { colors, fonts, fontSizes } = useTheme();
  const toast = useToast();
  const startFold = normaliseFold(initialFold);
  const [picked, setPicked] = useState(String(initialValue ?? ACCENTS[0][1]));
  const [pickedFold, setPickedFold] = useState(startFold);
  const [saving, setSaving] = useState(false);
  const error = HEX.test(picked.trim()) ? null : 'Use a 6-digit #hex colour';
  const tint = error ? String(initialValue ?? ACCENTS[0][1]) : picked.trim().toLowerCase();
  const pair = pairName(pickedFold, tint);

  useEffect(() => {
    if (open && initialValue) setPicked(String(initialValue));
  }, [open, initialValue]);

  useEffect(() => {
    if (open) setPickedFold(startFold);
  }, [open, startFold]);

  const handleSave = async () => {
    if (error) return;
    const accent = picked.trim().toLowerCase();
    const changes = {};
    if (pickedFold !== startFold) changes.fold = pickedFold;
    if (accent !== String(initialValue ?? '').trim().toLowerCase()) changes.accent = accent;
    if (!Object.keys(changes).length) {
      onClose?.();
      return;
    }
    setSaving(true);
    try {
      await onSave?.(changes);
      toast({ title: 'Appearance saved', duration: 1400 });
      onClose?.();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e), duration: 2400 });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Appearance"
      subtitle={`@${profileName ?? ''} · object and colour`}
      primaryAction={{ label: 'Save appearance', onPress: handleSave, disabled: !!error, loading: saving }}
    >
      <ScrollView keyboardShouldPersistTaps="handled">
        <View style={{ paddingHorizontal: space.s7, paddingTop: space.s3, gap: space.s3 }}>
          <Eyebrow>Object</Eyebrow>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
            {FOLD_IDS.map((id) => {
              const sel = pickedFold === id;
              return (
                <Pressable
                  key={id}
                  accessibilityRole="button"
                  accessibilityLabel={id}
                  accessibilityState={{ selected: sel }}
                  onPress={() => setPickedFold(id)}
                  style={{ width: `${100 / 6}%`, minHeight: 56, alignItems: 'center', justifyContent: 'center' }}
                >
                  <View
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: radii.xs,
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderWidth: sel ? 2 : 0.5,
                      borderColor: sel ? colors.ink : colors.line2,
                    }}
                  >
                    <Fold fold={id} color={tint} size={28} />
                  </View>
                </Pressable>
              );
            })}
          </View>
        </View>
        <View style={{ paddingHorizontal: space.s7, paddingTop: space.s5, gap: space.s3 }}>
          <Eyebrow>Colour</Eyebrow>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
            {ACCENTS.map(([name, hex]) => {
              const sel = selectedAccent(picked) === hex.toLowerCase();
              return (
                <Pressable
                  key={hex}
                  accessibilityRole="button"
                  accessibilityLabel={name}
                  accessibilityState={{ selected: sel }}
                  onPress={() => setPicked(hex)}
                  style={{ width: `${100 / 6}%`, minHeight: 56, alignItems: 'center', justifyContent: 'center' }}
                >
                  <View
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: radii.xs,
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderWidth: sel ? 2 : 0.5,
                      borderColor: sel ? colors.ink : colors.line2,
                    }}
                  >
                    <View style={{ width: 28, height: 28, borderRadius: radii.xs, backgroundColor: hex }} />
                  </View>
                </Pressable>
              );
            })}
          </View>
        </View>
        <View
          style={{
            paddingHorizontal: space.s8,
            paddingTop: space.s4,
            flexDirection: 'row',
            alignItems: 'center',
            gap: space.s6,
          }}
        >
          <Fold fold={pickedFold} color={tint} size={40} />
          <View style={{ flex: 1, gap: 2 }}>
            <Text
              style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink }}
            >
              {pair.charAt(0).toUpperCase() + pair.slice(1)}
            </Text>
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
              {`fold: ${pickedFold} · accent: ${tint}`}
            </Text>
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Reset to ${DEFAULT_FOLD}`}
            onPress={() => setPickedFold(DEFAULT_FOLD)}
            style={{ minHeight: 44, minWidth: 44, justifyContent: 'center', paddingHorizontal: space.s3 }}
          >
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink2 }}>
              {`Reset to ${DEFAULT_FOLD}`}
            </Text>
          </Pressable>
        </View>
        <View style={{ paddingHorizontal: space.s8, paddingTop: space.s5, paddingBottom: space.s7, gap: space.s3 }}>
          <Field
            label="Custom hex"
            helper="6-digit #hex — overrides the curated set"
            value={picked}
            onChangeText={setPicked}
            mono
            autoCapitalize="none"
            autoCorrect={false}
            error={error}
          />
        </View>
      </ScrollView>
    </Sheet>
  );
}

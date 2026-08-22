import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { ACCENTS } from '../../../../common/accents.mjs';
import { radii, space } from '../../theme/tokens';

import { Field } from '../../components/Field';
import { Sheet } from '../../components/Sheet';
import { useToast } from '../../components/Toast';
import { useTheme } from '../../theme/ThemeContext';

export function AccentSheet({ open, onClose, profileName, initialValue, onSave }) {
  const { colors, fonts, fontSizes } = useTheme();
  const toast = useToast();
  const [picked, setPicked] = useState(initialValue ?? ACCENTS[2][1]);

  useEffect(() => {
    if (open && initialValue) setPicked(initialValue);
  }, [open, initialValue]);

  const handleSave = async () => {
    try {
      await onSave?.(picked);
      toast({ title: 'Accent saved', duration: 1400 });
      onClose?.();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e), duration: 2400 });
    }
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Accent"
      subtitle={`@${profileName ?? ''} · identity color`}
      primaryAction={{ label: 'Save accent', onPress: handleSave }}
    >
      <View
        style={{
          paddingHorizontal: space.s7,
          paddingTop: space.s3,
          paddingBottom: space.s5,
          flexDirection: 'row',
          flexWrap: 'wrap',
        }}
      >
        {ACCENTS.map(([name, hex]) => {
          const sel = picked.toLowerCase() === hex.toLowerCase();
          return (
            <Pressable
              key={hex}
              onPress={() => setPicked(hex)}
              style={{
                width: '25%',
                paddingVertical: space.s4,
                alignItems: 'center',
                gap: space.s4,
              }}
            >
              <View
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: radii.md,
                  transform: [{ rotate: '45deg' }],
                  backgroundColor: hex,
                  borderWidth: sel ? 2 : 0.5,
                  borderColor: sel ? colors.bgPane : 'rgba(0,0,0,0.18)',
                  shadowColor: colors.ink,
                  shadowOpacity: sel ? 1 : 0,
                  shadowRadius: 0,
                  shadowOffset: { width: 0, height: 0 },
                  elevation: sel ? 4 : 0,
                }}
              />
              <Text
                style={{
                  fontFamily: fonts.sans.medium,
                  fontSize: fontSizes.xs,
                  color: sel ? colors.ink : colors.ink3,
                }}
              >
                {name}
              </Text>
            </Pressable>
          );
        })}
      </View>
      <View style={{ paddingHorizontal: space.s8, paddingTop: space.s3, paddingBottom: space.s7, gap: space.s3 }}>
        <Field
          label="Custom hex"
          helper="6-digit #hex — overrides the curated set"
          value={picked}
          onChangeText={setPicked}
          mono
          autoCapitalize="none"
          autoCorrect={false}
        />
      </View>
    </Sheet>
  );
}

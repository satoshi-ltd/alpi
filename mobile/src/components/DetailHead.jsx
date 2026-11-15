import { Pressable, Text, View } from 'react-native';
import { mobile, space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';
import { code } from '../theme/code';
import { copyText } from '../lib/clipboard';
import { detailTitleStyle } from './detailTitle';
import { Icon } from './Icon';
import { useToast } from './Toast';

export function DetailHead({ title, state = null, stateTone = null, id = null, right = null }) {
  const theme = useTheme();
  const { colors, fonts, fontSizes } = theme;
  const toast = useToast();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: space.s2 }}>
      <View style={{ flex: 1, gap: space.s1 }}>
        <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: space.s2, flexWrap: 'wrap' }}>
          <Text accessibilityRole="header" style={detailTitleStyle(theme)}>{title}</Text>
          {state ? (
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: stateTone === 'danger' ? colors.dangerText : colors.ink3 }}>{state}</Text>
          ) : null}
        </View>
        {id ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s1, marginVertical: -space.s4 }}>
            <Text selectable numberOfLines={1} style={{ flexShrink: 1, ...code(fonts, fontSizes.sm), color: colors.ink3 }}>{id}</Text>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Copy ${id}`}
              onPress={async () => { if (await copyText(id)) toast({ message: 'Copied', kind: 'success' }); }}
              style={{ width: mobile.tap, height: mobile.tap, alignItems: 'center', justifyContent: 'center' }}
            >
              <Icon name="copy" size="xs" color={colors.ink3} />
            </Pressable>
          </View>
        ) : null}
      </View>
      {right}
    </View>
  );
}

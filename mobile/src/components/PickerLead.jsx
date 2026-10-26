import { View } from 'react-native';
import { space } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';
import { Dot } from './Dot';

export const PICKER_SLOT = 14;
export const PICKER_GAP = space.s5;
export const PICKER_TEXT_EDGE = space.s7 + PICKER_SLOT + PICKER_GAP;

export function PickerLead({ selected, color }) {
  const { colors } = useTheme();
  return (
    <View style={{ width: PICKER_SLOT, alignItems: 'center' }}>
      {selected ? <Dot color={color ?? colors.accent} /> : null}
    </View>
  );
}

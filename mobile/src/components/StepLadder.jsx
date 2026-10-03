import { Text, View } from 'react-native';

import { Icon } from './Icon';
import { useTheme } from '../theme/ThemeContext';
import { radii, space } from '../theme/tokens';

export function StepLadder({ steps }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ gap: space.s3 }} accessibilityRole="list">
      {steps.map(({ id, state, label }) => {
        const tone = state === 'fail' ? colors.dangerText : state === 'todo' ? colors.ink3 : colors.ink;
        return (
          <View key={id} data-state={state} accessibilityLabel={`${label}, ${state}`} style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
            <View style={{ width: 16, alignItems: 'center' }}>
              {state === 'done' ? <Icon name="check" size="sm" color={colors.ink} />
                : state === 'fail' ? <Icon name="x" size="sm" color={colors.danger} />
                  : <View style={{ width: 6, height: 6, borderRadius: radii.xs, backgroundColor: state === 'now' ? colors.ink2 : colors.ink4 }} />}
            </View>
            <Text style={{ flex: 1, fontFamily: state === 'todo' ? fonts.sans.regular : fonts.sans.medium, fontSize: fontSizes.md, color: tone }}>{label}</Text>
          </View>
        );
      })}
    </View>
  );
}

export function ladderSteps(order, current, failedAt, labelFor) {
  const index = order.indexOf(failedAt ?? current);
  return order.map((id, i) => ({
    id,
    label: labelFor(id),
    state: failedAt
      ? i < index ? 'done' : i === index ? 'fail' : 'todo'
      : current === 'done' ? 'done' : i < index ? 'done' : i === index ? 'now' : 'todo',
  }));
}

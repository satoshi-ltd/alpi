import { useEffect, useState } from 'react';
import { Dimensions, Keyboard, Platform, View } from 'react-native';

const SHOW = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
const HIDE = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';

function occupied(e) {
  const frame = e?.endCoordinates;
  if (!frame) return 0;
  const screen = Dimensions.get('screen').height;
  return Math.max(0, Math.min(screen, screen - frame.screenY));
}

export function KeyboardPane({ children, style }) {
  const [pad, setPad] = useState(0);
  useEffect(() => {
    const show = Keyboard.addListener(SHOW, (e) => setPad(occupied(e)));
    const hide = Keyboard.addListener(HIDE, () => setPad(0));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);
  return <View style={[style ?? { flex: 1 }, { paddingBottom: pad }]}>{children}</View>;
}

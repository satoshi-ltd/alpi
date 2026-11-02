import { Keyboard, Pressable } from 'react-native';

export function KeyboardDismissArea({ children }) {
  return (
    <Pressable style={{ flex: 1 }} onPress={Keyboard.dismiss} accessible={false} focusable={false}>
      {children}
    </Pressable>
  );
}

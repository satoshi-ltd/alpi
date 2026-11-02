import { useLayoutEffect } from 'react';
import { Keyboard } from 'react-native';

export function useDismissKeyboard(open) {
  useLayoutEffect(() => {
    if (open) Keyboard.dismiss();
  }, [open]);
}

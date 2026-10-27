import { useEffect, useState } from 'react';
import { Keyboard, Platform, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { firstRunEdge } from '../lib/firstRun';

const SHOW = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
const HIDE = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';

export function useKeyboardOpen() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const show = Keyboard.addListener(SHOW, () => setOpen(true));
    const hide = Keyboard.addListener(HIDE, () => setOpen(false));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);
  return open;
}

export function useFirstRunLayout() {
  const { width, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  return { edge: firstRunEdge(width, height), insets, width, height };
}

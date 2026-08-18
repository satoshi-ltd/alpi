import { usePathname } from 'expo-router';
import { useRef } from 'react';
import { useWindowDimensions } from 'react-native';

import { isFullBleed, isTwoPane, nextTwoPane } from '../lib/panes';

export function useTwoPane() {
  const { width, height } = useWindowDimensions();
  const pathname = usePathname();
  const prev = useRef(isTwoPane(width, height));
  prev.current = nextTwoPane(prev.current, width, height);

  return prev.current && !isFullBleed(pathname);
}

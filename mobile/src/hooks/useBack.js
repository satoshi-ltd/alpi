import { usePathname, useRouter } from 'expo-router';
import { useCallback, useEffect } from 'react';
import { BackHandler } from 'react-native';

import { backFallback, isFullBleed } from '../lib/panes';

export function useBack() {
  const router = useRouter();
  const pathname = usePathname();

  return useCallback(() => {
    if (router.canGoBack?.()) router.back();
    else router.replace(backFallback(pathname));
  }, [router, pathname]);
}

// Two panes navigate with replace, so after a fold to one pane the stack can hold a detail with nothing beneath it.
export function useSystemBack(twoPane) {
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    if (twoPane) return undefined;
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (pathname === '/' || isFullBleed(pathname) || router.canGoBack?.()) return false;
      router.replace(backFallback(pathname));
      return true;
    });
    return () => sub.remove();
  }, [twoPane, router, pathname]);
}

export function SystemBack({ twoPane }) {
  useSystemBack(twoPane);
  return null;
}

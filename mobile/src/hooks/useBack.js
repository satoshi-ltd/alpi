import { usePathname, useRouter } from 'expo-router';
import { useCallback } from 'react';

import { backFallback } from '../lib/panes';

export function useBack() {
  const router = useRouter();
  const pathname = usePathname();

  return useCallback(() => {
    if (router.canGoBack?.()) router.back();
    else router.replace(backFallback(pathname));
  }, [router, pathname]);
}

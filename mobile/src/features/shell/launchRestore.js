import { usePathname, useRouter } from 'expo-router';
import { useEffect } from 'react';

import { useEndpoint } from '../../lib/EndpointContext';
import { isHome, openVerb, resumePath } from '../../lib/panes';

let pending = true;

export function _resetLaunchRestore() {
  pending = true;
}

export function useLaunchRestore({ items, twoPane }) {
  const router = useRouter();
  const pathname = usePathname();
  const { endpoint } = useEndpoint();
  const target = twoPane && endpoint ? resumePath(items) : null;

  useEffect(() => {
    if (!pending) return;
    if (!twoPane || !isHome(pathname)) {
      pending = false;
      return;
    }
    if (!target) return;
    pending = false;
    router[openVerb({ twoPane, pathname })](target);
  }, [target, twoPane, pathname, router]);
}

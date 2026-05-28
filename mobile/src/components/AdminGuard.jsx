import { useRouter } from 'expo-router';
import { useEffect } from 'react';

import { useActiveRole } from '../hooks/useActiveRole';

// Strict route gate — role null (probe pending) renders null too so admin RPCs don't fire on first mount; member triggers back/replace.
export function AdminGuard({ fallbackHref = '/', children }) {
  const role = useActiveRole();
  const router = useRouter();
  useEffect(() => {
    if (role !== 'member') return;
    if (router.canGoBack?.()) router.back();
    else router.replace(fallbackHref);
  }, [role, router, fallbackHref]);
  if (role !== 'admin') return null;
  return children;
}

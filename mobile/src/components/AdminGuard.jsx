import { useEffect } from 'react';

import { useActiveRole } from '../hooks/useActiveRole';
import { useBack } from '../hooks/useBack';

// Strict route gate — role null (probe pending) renders null too so admin RPCs don't fire on first mount.
export function AdminGuard({ children }) {
  const role = useActiveRole();
  const goBack = useBack();
  useEffect(() => {
    if (role === 'member') goBack();
  }, [role, goBack]);
  if (role !== 'admin') return null;
  return children;
}

import { useEndpoint } from '../lib/EndpointContext';

export function useActiveRole() {
  const { activeRole } = useEndpoint();
  return activeRole ?? null;
}

// Chrome-permissive: null counts as admin so probe latency doesn't flicker the gear icons.
export function useCanAdminEarly() {
  const role = useActiveRole();
  return role === 'admin' || role == null;
}

// Strict — `null` denies. Pair with <AdminGuard> on routes so admin RPCs don't fire while probe pending.
export function useIsAdmin() {
  const role = useActiveRole();
  return role === 'admin';
}

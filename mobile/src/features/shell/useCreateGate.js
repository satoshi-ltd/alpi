import { useEffect } from 'react';

import { useToast } from '../../components/Toast';
import { useIsAdmin } from '../../hooks/useActiveRole';

export const NEW_PROFILE = 'newProfile';
export const NEW_WORKGROUP = 'newWorkgroup';

export function useCreateGate(sheet, onDeny) {
  const isAdmin = useIsAdmin();
  const toast = useToast();
  const denied = !isAdmin && (sheet === NEW_PROFILE || sheet === NEW_WORKGROUP);

  useEffect(() => {
    if (!denied) return;
    onDeny();
    toast({
      title: 'Admin only',
      message: 'Ask an admin to create profiles and workgroups on this daemon.',
    });
  }, [denied, onDeny, toast]);

  return isAdmin;
}

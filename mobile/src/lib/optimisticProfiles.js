import { useSyncExternalStore } from 'react';
import { profileEditsVersion, subscribeProfileEdits } from '../../../common/optimisticProfiles.mjs';

export * from '../../../common/optimisticProfiles.mjs';

export function useProfileEdits() {
  return useSyncExternalStore(subscribeProfileEdits, profileEditsVersion);
}

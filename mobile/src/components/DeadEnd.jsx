import { useRouter } from 'expo-router';
import { useState } from 'react';

import { EMPTY } from '../../../common/emptyCopy.mjs';
import { ConnectionSheet } from '../features/sheets/ConnectionSheet';
import { EmptyState } from './EmptyState';
import { LoadFailed } from './LoadFailed';

const ACTIONS = {
  inbox: 'Back to inbox',
  pair: 'Pair this phone',
  connection: 'Switch connection',
};

// A read that failed proves nothing is missing, so it offers Retry instead of claiming the row is gone.
export function DeadEnd({ copy, action = 'inbox', error = null, onRetry = null, label = 'this page' }) {
  const router = useRouter();
  const [sheetOpen, setSheetOpen] = useState(false);
  if (error) return <LoadFailed label={label} error={error} onRetry={onRetry} />;
  const { title, hint } = EMPTY[copy];
  const onPress = () => {
    if (action === 'pair') {
      router.push('/pair');
    } else if (action === 'connection') {
      setSheetOpen(true);
    } else {
      if (router.canDismiss?.()) router.dismissAll();
      router.replace('/');
    }
  };
  return (
    <>
      <EmptyState alert title={title} detail={hint} action={{ label: ACTIONS[action], onPress }} />
      {action === 'connection' ? <ConnectionSheet open={sheetOpen} onClose={() => setSheetOpen(false)} /> : null}
    </>
  );
}

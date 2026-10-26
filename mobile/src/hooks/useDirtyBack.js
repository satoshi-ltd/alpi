import { useNavigation } from 'expo-router';
import { useCallback, useEffect, useRef } from 'react';

import { useConfirm } from '../components/ConfirmProvider';

export function useDirtyBack(isDirty, onConfirmLeave) {
  const navigation = useNavigation();
  const confirm = useConfirm();
  const dirtyRef = useRef(isDirty);
  dirtyRef.current = isDirty;
  const discardingRef = useRef(false);
  const promptingRef = useRef(false);

  useEffect(() => {
    navigation?.setOptions?.({ gestureEnabled: !isDirty });
    return () => navigation?.setOptions?.({ gestureEnabled: true });
  }, [navigation, isDirty]);

  useEffect(() => {
    const sub = navigation?.addListener?.('beforeRemove', (e) => {
      if (!dirtyRef.current || discardingRef.current) return;
      e.preventDefault();
      if (promptingRef.current) return;
      promptingRef.current = true;
      confirm({
        title: 'Discard changes?',
        body: 'You have unsaved edits.',
        confirmLabel: 'Discard',
        cancelLabel: 'Keep editing',
      }).then((discard) => {
        promptingRef.current = false;
        if (!discard) return;
        discardingRef.current = true;
        navigation.dispatch(e.data.action);
      });
    });
    return sub;
  }, [navigation, confirm]);

  return useCallback(() => {
    onConfirmLeave();
    return true;
  }, [onConfirmLeave]);
}

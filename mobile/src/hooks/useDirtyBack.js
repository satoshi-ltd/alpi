// Intercepts hardware/navigation back when the form has unsaved changes and surfaces a "Discard / Keep editing" confirm.

import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, BackHandler } from 'react-native';

export function useDirtyBack(isDirty, onConfirmLeave) {
  const [pendingConfirm, setPendingConfirm] = useState(false);

  const ask = useCallback(() => {
    if (!isDirty) {
      onConfirmLeave();
      return true;
    }
    if (pendingConfirm) return true;
    setPendingConfirm(true);
    Alert.alert(
      'Discard changes?',
      'You have unsaved edits.',
      [
        { text: 'Keep editing', style: 'cancel', onPress: () => setPendingConfirm(false) },
        {
          text: 'Discard',
          style: 'destructive',
          onPress: () => {
            setPendingConfirm(false);
            onConfirmLeave();
          },
        },
      ],
      { cancelable: true, onDismiss: () => setPendingConfirm(false) },
    );
    return true;
  }, [isDirty, pendingConfirm, onConfirmLeave]);

  useFocusEffect(
    useCallback(() => {
      const sub = BackHandler.addEventListener('hardwareBackPress', ask);
      return () => sub.remove();
    }, [ask]),
  );

  return ask;
}

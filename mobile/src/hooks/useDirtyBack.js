import { useNavigation } from 'expo-router';
import { useCallback, useEffect, useRef } from 'react';
import { Alert } from 'react-native';

export function useDirtyBack(isDirty, onConfirmLeave) {
  const navigation = useNavigation();
  const dirtyRef = useRef(isDirty);
  dirtyRef.current = isDirty;
  const discardingRef = useRef(false);
  const promptingRef = useRef(false);

  useEffect(() => {
    navigation?.setOptions?.({ gestureEnabled: !isDirty });
  }, [navigation, isDirty]);

  useEffect(() => {
    const sub = navigation?.addListener?.('beforeRemove', (e) => {
      if (!dirtyRef.current || discardingRef.current) return;
      e.preventDefault();
      if (promptingRef.current) return;
      promptingRef.current = true;
      Alert.alert(
        'Discard changes?',
        'You have unsaved edits.',
        [
          { text: 'Keep editing', style: 'cancel', onPress: () => { promptingRef.current = false; } },
          {
            text: 'Discard',
            style: 'destructive',
            onPress: () => {
              promptingRef.current = false;
              discardingRef.current = true;
              navigation.dispatch(e.data.action);
            },
          },
        ],
        { cancelable: true, onDismiss: () => { promptingRef.current = false; } },
      );
    });
    return sub;
  }, [navigation]);

  return useCallback(() => {
    onConfirmLeave();
    return true;
  }, [onConfirmLeave]);
}

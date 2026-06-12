import { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet } from 'react-native';
import { space } from '../../theme/tokens';
import { subscribeReadAloud, clearReadAloud } from '../../lib/readAloud';

function Bar({ accent, delay }) {
  const h = useRef(new Animated.Value(4)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(h, { toValue: 14, duration: 450, delay, useNativeDriver: false }),
        Animated.timing(h, { toValue: 4, duration: 450, useNativeDriver: false }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [h, delay]);
  return <Animated.View style={[styles.bar, { height: h, backgroundColor: accent }]} />;
}

export function SoundWave({ accent }) {
  const [state, setState] = useState(null);
  useEffect(
    () => subscribeReadAloud((s) =>
      setState(s?.kind === 'playing' || s?.kind === 'loading' ? s : null)),
    [],
  );
  if (!state) return null;
  const c = state.accent || accent;
  return (
    <Pressable onPress={clearReadAloud} hitSlop={8} accessibilityLabel="silence read-aloud" style={styles.wave}>
      <Bar accent={c} delay={0} />
      <Bar accent={c} delay={150} />
      <Bar accent={c} delay={300} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wave: { flexDirection: 'row', alignItems: 'center', gap: 2, height: 18, paddingHorizontal: space.s2 },
  bar: { width: 2.5, borderRadius: 2 },
});

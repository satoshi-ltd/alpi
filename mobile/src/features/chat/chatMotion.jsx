import { useCallback, useEffect, useRef } from 'react';
import * as ReactNative from 'react-native';
import Animated, { FadeIn } from 'react-native-reanimated';

export const ENTER_MS = 180;

export function listDismissMode() {
  let os = null;
  try {
    os = ReactNative.Platform?.OS ?? null;
  } catch {
    os = null;
  }
  return os === 'ios' ? 'interactive' : 'on-drag';
}

// Rank guards against older pages loading in above the fold; only rows ranked past the first ready page may fade.
export function useSeenIds(ids, ready) {
  const seen = useRef(new Set());
  const top = useRef(-Infinity);
  const wasReady = useRef(false);
  if (ready && !wasReady.current) {
    for (const id of ids) {
      seen.current.add(id);
      if (typeof id === 'number' && id > top.current) top.current = id;
    }
  }
  wasReady.current = ready;
  const isFresh = useCallback(
    (id, rank = id) => wasReady.current && !seen.current.has(id) && !(rank <= top.current),
    [],
  );
  const markSeen = useCallback((id) => { seen.current.add(id); }, []);
  return { isFresh, markSeen };
}

export function ownConfirmation(post, ownPubkey) {
  return !post?.pending && ownPubkey != null && post?.from_pubkey === ownPubkey;
}

export function EnterOnce({ id, fresh, onSeen, style, children }) {
  useEffect(() => { onSeen(id); }, [id, onSeen]);
  return (
    <Animated.View style={style} entering={fresh ? FadeIn.duration(ENTER_MS) : undefined}>
      {children}
    </Animated.View>
  );
}

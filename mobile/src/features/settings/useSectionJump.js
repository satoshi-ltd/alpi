import { useRef, useState } from 'react';

import { sectionAt } from './jumpSections';

const JUMP_SETTLE_MS = 900;

export function useSectionJump() {
  const scrollRef = useRef(null);
  const offsets = useRef({});
  const settleAt = useRef(0);
  const [section, setSection] = useState('overview');
  const anchor = (key) => ({ onLayout: (e) => { offsets.current[key] = e.nativeEvent.layout.y; } });
  const jump = (key) => {
    const y = offsets.current[key];
    if (typeof y !== 'number') return;
    settleAt.current = performance.now() + JUMP_SETTLE_MS;
    setSection(key);
    scrollRef.current?.scrollTo({ y: Math.max(0, y - 4), animated: true });
  };
  const onScroll = (e) => {
    if (performance.now() < settleAt.current) return;
    setSection(sectionAt(offsets.current, e.nativeEvent.contentOffset.y));
  };
  const onScrollBeginDrag = () => { settleAt.current = 0; };
  return { scrollRef, anchor, jump, section, onScroll, onScrollBeginDrag };
}

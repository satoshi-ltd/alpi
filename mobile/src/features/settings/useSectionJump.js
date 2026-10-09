import { useRef, useState } from 'react';

import { sectionAt } from './jumpSections';

export function useSectionJump() {
  const scrollRef = useRef(null);
  const offsets = useRef({});
  const [section, setSection] = useState('overview');
  const anchor = (key) => ({ onLayout: (e) => { offsets.current[key] = e.nativeEvent.layout.y; } });
  const jump = (key) => {
    const y = offsets.current[key];
    if (typeof y === 'number') scrollRef.current?.scrollTo({ y: Math.max(0, y - 4), animated: true });
  };
  const onScroll = (e) => setSection(sectionAt(offsets.current, e.nativeEvent.contentOffset.y));
  return { scrollRef, anchor, jump, section, onScroll };
}

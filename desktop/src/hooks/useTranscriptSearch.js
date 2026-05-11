import { useCallback, useEffect, useRef, useState } from "react";

const HL_NAME = "alpi-search";
const HL_CURRENT_NAME = "alpi-search-current";

const supportsHighlights =
  typeof CSS !== "undefined" &&
  typeof CSS.highlights !== "undefined" &&
  typeof Highlight !== "undefined";

export function useTranscriptSearch(scrollRef, open) {
  const [query, setQuery] = useState("");
  const [ranges, setRanges] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  const searchHL = useRef(null);
  const currentHL = useRef(null);

  useEffect(() => {
    if (!supportsHighlights) return;
    searchHL.current = new Highlight();
    currentHL.current = new Highlight();
    CSS.highlights.set(HL_NAME, searchHL.current);
    CSS.highlights.set(HL_CURRENT_NAME, currentHL.current);
    return () => {
      CSS.highlights.delete(HL_NAME);
      CSS.highlights.delete(HL_CURRENT_NAME);
      searchHL.current = null;
      currentHL.current = null;
    };
  }, []);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setRanges([]);
      setCurrentIndex(0);
    }
  }, [open]);

  useEffect(() => {
    const root = scrollRef.current;
    if (!root || !open || !query.trim()) {
      setRanges([]);
      setCurrentIndex(0);
      return;
    }
    const found = findRanges(root, query);
    setRanges(found);
    setCurrentIndex(0);
  }, [scrollRef, open, query]);

  useEffect(() => {
    const s = searchHL.current;
    const c = currentHL.current;
    if (!s || !c) return;
    s.clear();
    c.clear();
    ranges.forEach((r, i) => {
      if (i === currentIndex) c.add(r);
      else s.add(r);
    });
    const current = ranges[currentIndex];
    if (current && scrollRef.current) {
      scrollRangeIntoView(scrollRef.current, current);
    }
  }, [ranges, currentIndex, scrollRef]);

  const next = useCallback(() => {
    setCurrentIndex((i) => (ranges.length === 0 ? 0 : (i + 1) % ranges.length));
  }, [ranges.length]);

  const prev = useCallback(() => {
    setCurrentIndex((i) =>
      ranges.length === 0 ? 0 : (i - 1 + ranges.length) % ranges.length,
    );
  }, [ranges.length]);

  const reset = useCallback(() => {
    setQuery("");
    setRanges([]);
    setCurrentIndex(0);
  }, []);

  return {
    query,
    setQuery,
    total: ranges.length,
    currentIndex,
    next,
    prev,
    reset,
  };
}

function findRanges(root, query) {
  const needle = query.toLowerCase();
  if (!needle) return [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue) return NodeFilter.FILTER_REJECT;
      const parent = node.parentElement;
      if (!parent) return NodeFilter.FILTER_REJECT;
      if (parent.closest("input, textarea, button, [role='search']")) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  const ranges = [];
  let node;
  while ((node = walker.nextNode())) {
    const text = node.nodeValue;
    const lower = text.toLowerCase();
    let pos = 0;
    while ((pos = lower.indexOf(needle, pos)) !== -1) {
      const range = new Range();
      range.setStart(node, pos);
      range.setEnd(node, pos + needle.length);
      ranges.push(range);
      pos += needle.length;
    }
  }
  return ranges;
}

function scrollRangeIntoView(container, range) {
  if (!container || !range) return;
  const rect = range.getBoundingClientRect();
  const cRect = container.getBoundingClientRect();
  const margin = 80;
  const above = rect.top < cRect.top + margin;
  const below = rect.bottom > cRect.bottom - margin;
  if (above) {
    container.scrollBy({
      top: rect.top - cRect.top - margin,
      behavior: "smooth",
    });
  } else if (below) {
    container.scrollBy({
      top: rect.bottom - cRect.bottom + margin,
      behavior: "smooth",
    });
  }
}

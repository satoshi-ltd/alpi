import { createContext, createElement, useCallback, useContext, useLayoutEffect, useMemo, useRef } from "react";

const layers = [];
const OverlayAncestors = createContext([]);

export function OverlayScope({ overlay, children }) {
  const ancestors = useContext(OverlayAncestors);
  const value = useMemo(() => [...ancestors, overlay], [ancestors, overlay]);
  return createElement(OverlayAncestors.Provider, { value }, children);
}
const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]';

function focusable(root) {
  return [...(root?.querySelectorAll(FOCUSABLE) ?? [])].filter((el) =>
    el.tabIndex >= 0 && !el.matches(':disabled') && !el.closest('[hidden], [inert], [aria-hidden="true"]') &&
    getComputedStyle(el).display !== "none" && getComputedStyle(el).visibility !== "hidden",
  );
}

function onKey(event) {
  const top = layers.at(-1);
  if (!top || event.defaultPrevented) return;
  if (event.key === "Escape") {
    event.preventDefault();
    event.stopImmediatePropagation();
    top.close.current?.();
    return;
  }
  if (event.key !== "Tab") return;
  const modalIndex = layers.findLastIndex((layer) => layer.modal);
  if (modalIndex < 0) return;
  const activeLayers = layers.slice(modalIndex);
  const items = [...new Set(activeLayers.flatMap((layer) => focusable(layer.ref.current)))];
  const first = items[0];
  const last = items.at(-1);
  const active = document.activeElement;
  if (!first || !items.includes(active) || (event.shiftKey ? active === first : active === last)) {
    event.preventDefault();
    (event.shiftKey ? last : first)?.focus();
    if (!first) activeLayers[0].ref.current?.focus();
  }
}

export function useOverlay({ open, onClose, ref, modal = false }) {
  const ancestors = useContext(OverlayAncestors);
  // Capture the opener before child autofocus runs during commit.
  const opener = document.activeElement;
  const close = useRef(onClose);
  const entry = useRef(null);
  const isTop = useCallback(() => layers.at(-1) === entry.current, []);

  useLayoutEffect(() => {
    close.current = onClose;
  }, [onClose]);

  useLayoutEffect(() => {
    if (!open) return;
    const previous = opener;
    const layer = { ref, close, modal, ancestors };
    entry.current = layer;
    const descendant = layers.findIndex((item) => item.ancestors.includes(isTop));
    layers.splice(descendant < 0 ? layers.length : descendant, 0, layer);
    if (layers.length === 1) window.addEventListener("keydown", onKey);
    if (modal && layers.at(-1) === layer && !ref.current?.contains(document.activeElement)) {
      (focusable(ref.current)[0] ?? ref.current)?.focus();
    }
    return () => {
      const index = layers.indexOf(layer);
      if (index >= 0) layers.splice(index, 1);
      if (!layers.length) window.removeEventListener("keydown", onKey);
      const shouldRestore = document.activeElement === document.body || ref.current?.contains(document.activeElement);
      if (shouldRestore) setTimeout(() => {
        if (previous?.isConnected && (document.activeElement === document.body || !document.activeElement?.isConnected)) {
          previous.focus?.();
        }
      }, 0);
    };
  }, [open, ref, modal, ancestors, isTop]);

  return isTop;
}

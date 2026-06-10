import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import styles from "./Tooltip.module.css";

const SHOW_DELAY_MS = 200;

export default function Tooltip({
  text,
  direction = "down",
  align = "center",
  disabled = false,
  children,
}) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState(null);
  const triggerRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  if (!text || disabled) return children;

  function compute() {
    if (!triggerRef.current) return;
    setCoords(triggerRef.current.getBoundingClientRect());
  }

  function handleEnter() {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      compute();
      setOpen(true);
    }, SHOW_DELAY_MS);
  }

  function handleLeave() {
    clearTimeout(timerRef.current);
    setOpen(false);
  }

  return (
    <>
      <span
        ref={triggerRef}
        className={styles.wrap}
        onMouseEnter={handleEnter}
        onMouseLeave={handleLeave}
        onFocus={handleEnter}
        onBlur={handleLeave}
      >
        {children}
      </span>
      {open && coords &&
        createPortal(
          <span
            className={`anim-fade ${styles.tooltip}`}
            style={positionFor(coords, direction, align)}
          >
            {text}
          </span>,
          document.body,
        )}
    </>
  );
}

function positionFor(rect, direction, align) {
  const GAP = 6;
  if (direction === "right") {
    return {
      position: "fixed",
      left: rect.right + GAP,
      top: rect.top + rect.height / 2,
      transform: "translateY(-50%)",
    };
  }
  if (direction === "left") {
    return {
      position: "fixed",
      right: window.innerWidth - rect.left + GAP,
      top: rect.top + rect.height / 2,
      transform: "translateY(-50%)",
    };
  }
  const verticalKey = direction === "up" ? "bottom" : "top";
  const verticalValue =
    direction === "up"
      ? window.innerHeight - rect.top + GAP
      : rect.bottom + GAP;
  if (align === "start") {
    return { position: "fixed", left: rect.left, [verticalKey]: verticalValue };
  }
  if (align === "end") {
    return {
      position: "fixed",
      right: window.innerWidth - rect.right,
      [verticalKey]: verticalValue,
    };
  }
  return {
    position: "fixed",
    left: rect.left + rect.width / 2,
    transform: "translateX(-50%)",
    [verticalKey]: verticalValue,
  };
}

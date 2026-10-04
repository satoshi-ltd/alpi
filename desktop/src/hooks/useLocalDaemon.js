import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

export function useLocalDaemon({ enabled, onStarted }) {
  const [state, setState] = useState(null);
  const [phase, setPhase] = useState("idle");
  const [error, setError] = useState(null);
  const autoStartedRef = useRef(false);
  const onStartedRef = useRef(onStarted);
  onStartedRef.current = onStarted;
  const phaseRef = useRef(phase);
  phaseRef.current = phase;

  const detect = useCallback(async () => {
    try {
      const result = await invoke("local_daemon_state");
      const next = result?.state ?? "absent";
      setState(next);
      if (next === "running" && phaseRef.current !== "starting") onStartedRef.current?.();
      return next;
    } catch {
      setState("absent");
      return "absent";
    }
  }, []);

  const start = useCallback(async () => {
    setPhase("starting");
    setError(null);
    try {
      await invoke("local_daemon_start");
      setPhase("idle");
      setState("running");
      onStartedRef.current?.();
    } catch (e) {
      setError(String(e?.message ?? e));
      setPhase("failed");
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      autoStartedRef.current = false;
      setPhase("idle");
      setError(null);
      return undefined;
    }
    let cancelled = false;
    detect().then((next) => {
      if (cancelled || next !== "stopped" || autoStartedRef.current) return;
      autoStartedRef.current = true;
      start();
    });
    const onFocus = () => { if (phaseRef.current !== "starting") detect(); };
    window.addEventListener("focus", onFocus);
    return () => {
      cancelled = true;
      window.removeEventListener("focus", onFocus);
    };
  }, [enabled, detect, start]);

  return { state: enabled ? state : null, phase, error, start, detect };
}

import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

const LAUNCH_GRACE_MS = 15000;

export function useLocalDaemon({ enabled, onStarted }) {
  const [state, setState] = useState(null);
  const [phase, setPhase] = useState("idle");
  const [error, setError] = useState(null);
  const [launched, setLaunched] = useState(false);
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
      if (next === "running" && !["starting", "installing"].includes(phaseRef.current)) onStartedRef.current?.();
      return next;
    } catch {
      setState("absent");
      return "absent";
    }
  }, []);

  const start = useCallback(async () => {
    if (phaseRef.current === "starting") return;
    phaseRef.current = "starting";
    setPhase("starting");
    setError(null);
    setLaunched(false);
    try {
      await invoke("local_daemon_start");
      setLaunched(true);
      setPhase("idle");
      setState("running");
      onStartedRef.current?.();
    } catch (e) {
      setError(String(e?.message ?? e));
      setPhase("failed");
    }
  }, []);

  const install = useCallback(async () => {
    if (["installing", "starting"].includes(phaseRef.current)) return;
    phaseRef.current = "installing";
    setPhase("installing");
    setError(null);
    try {
      await invoke("local_daemon_install");
      await start();
    } catch (e) {
      setError(String(e?.message ?? e));
      setPhase("install-failed");
    }
  }, [start]);

  useEffect(() => {
    if (!enabled) {
      autoStartedRef.current = false;
      setLaunched(false);
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
    const onFocus = () => { if (!["starting", "installing"].includes(phaseRef.current)) detect(); };
    window.addEventListener("focus", onFocus);
    return () => {
      cancelled = true;
      window.removeEventListener("focus", onFocus);
    };
  }, [enabled, detect, start]);

  useEffect(() => {
    if (!launched) return undefined;
    const timer = setTimeout(() => setLaunched(false), LAUNCH_GRACE_MS);
    return () => clearTimeout(timer);
  }, [launched]);

  return { state: enabled ? state : null, phase, error, launched: enabled && launched, start, install, detect };
}

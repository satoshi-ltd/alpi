import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { ALPACA_FOLD } from "../../../common/folds.mjs";
import { ICON_ROLES } from "../../../common/iconRoles.mjs";
import { Button, Fold, Icon, IconBtn } from "../primitives/index.js";
import { safeUnlisten } from "../lib/tauri-listen.js";
import { trayModel } from "./trayModel.js";
import { useTrayTheme } from "./useTrayTheme.js";
import styles from "./TrayApp.module.css";

const CLOCK_MS = 30000;

const call = (command, args) => invoke(command, args).catch(() => {});

function useSnapshot() {
  const [snapshot, setSnapshot] = useState(null);
  const [shown, setShown] = useState(0);
  useEffect(() => {
    let cancelled = false;
    const unlistens = [];
    const load = () => invoke("tray_state").then((next) => { if (!cancelled && next) setSnapshot(next); }).catch(() => {});
    const subscribe = (name, handler) =>
      listen(name, handler)
        .then((fn) => {
          if (cancelled) safeUnlisten(fn);
          else unlistens.push(fn);
        })
        .catch(() => {});
    subscribe("tray-state", (event) => setSnapshot(event.payload ?? null));
    subscribe("tray-shown", () => {
      setShown((n) => n + 1);
      load();
    });
    load();
    return () => {
      cancelled = true;
      unlistens.forEach(safeUnlisten);
    };
  }, []);
  return [snapshot, shown];
}

function useClock(shown) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), CLOCK_MS);
    return () => clearInterval(id);
  }, [shown]);
  return now;
}

function CountRow({ item, onOpen }) {
  return (
    <button type="button" className={styles.line} onClick={onOpen} aria-label={`${item.label}, ${item.value}. Open alpi`}>
      <span className={styles.lineIcon} data-tone={item.danger ? "danger" : undefined}><Icon name={item.icon} /></span>
      <span className={styles.lineLabel}>{item.label}</span>
      <span className={styles.lineValue} data-tone={item.danger ? "danger" : undefined}>{item.value}</span>
      <span className={styles.chev}><Icon name="chevron-right" size="sm" /></span>
    </button>
  );
}

function NeedsRow({ row, onReview }) {
  return (
    <li className={styles.row} data-kind={row.kind}>
      <span className={styles.rowMain} onClick={() => onReview(row)}>
        <span className={styles.glyph}>
          <Fold fold={row.fold} color={row.accent || undefined} />
        </span>
        <span className={styles.text}>
          <span className={styles.rowTitle} title={row.title}>{row.title}</span>
          <span className={styles.rowSub}>{row.sub}</span>
        </span>
      </span>
      <Button size="sm" variant="secondary" aria-label={`Review: ${row.title}, ${row.sub}`} onClick={() => onReview(row)}>
        Review
      </Button>
    </li>
  );
}

export default function TrayApp() {
  useTrayTheme();
  const [snapshot, shown] = useSnapshot();
  const now = useClock(shown);
  const model = useMemo(() => trayModel(snapshot ?? { state: "connecting" }, now), [snapshot, now]);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(null);
  const frameRef = useRef(null);
  const lastHeight = useRef(0);

  const hide = useCallback(() => call("hide_tray"), []);
  const openAlpi = useCallback((deeplink = null) => call("show_main", { deeplink }), []);
  const review = useCallback((row) => openAlpi(row.deeplink), [openAlpi]);
  const start = useCallback(async () => {
    setStarting(true);
    setStartError(null);
    try {
      await invoke("start_alpi");
    } catch (error) {
      setStartError(String(error?.message ?? error));
    } finally {
      setStarting(false);
    }
  }, []);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        hide();
      }
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("blur", hide);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("blur", hide);
    };
  }, [hide]);

  useEffect(() => {
    const frame = frameRef.current;
    if (!frame || typeof ResizeObserver === "undefined") return undefined;
    const report = () => {
      const height = Math.ceil(frame.getBoundingClientRect().height);
      if (!height || height === lastHeight.current) return;
      lastHeight.current = height;
      call("resize_tray", { height });
    };
    const observer = new ResizeObserver(report);
    observer.observe(frame);
    report();
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (shown > 0) frameRef.current?.focus({ preventScroll: true });
  }, [shown]);

  const state = starting ? "starting" : model.state;
  const title = starting ? "Starting alpi…" : model.title;
  const sub = starting ? "Waiting for the daemon" : startError ?? model.sub;
  const busy = starting ? "Start requested" : model.busy;

  return (
    <div className={styles.frame} ref={frameRef} tabIndex={-1}>
      <main className={styles.pop} aria-label="Alpi status" data-state={state}>
        <header className={styles.head}>
          <Fold fold={ALPACA_FOLD} size={28} />
          <div className={styles.headText}>
            <h1 className={styles.title} aria-live="polite">{title}</h1>
            {model.next && !starting && !startError ? (
              <p className={styles.sub} data-next>
                <span className={styles.nextLead}>Next:&nbsp;</span>
                <span className={styles.nextTitle}>{model.next.title}</span>
                <span className={styles.nextWhen}>&nbsp;·&nbsp;{model.next.when}</span>
              </p>
            ) : (
              <p className={styles.sub}>{sub}</p>
            )}
          </div>
          {model.start && !starting ? (
            <Button size="sm" variant="primary" onClick={start}>Start alpi</Button>
          ) : null}
        </header>
        {model.rows.length > 0 ? (
          <section className={styles.section} aria-label="Needs you">
            <ul className={styles.list}>
              {model.rows.map((row) => <NeedsRow key={row.key} row={row} onReview={review} />)}
            </ul>
            {model.more > 0 ? (
              <button type="button" className={styles.line} onClick={() => openAlpi()}>
                <span className={styles.lineLabel}>{model.more} more · Open alpi</span>
                <span className={styles.chev}><Icon name="chevron-right" size="sm" /></span>
              </button>
            ) : null}
          </section>
        ) : null}
        {model.counts.length > 0 ? (
          <section className={styles.section} aria-label="Counts">
            {model.counts.map((item) => <CountRow key={item.key} item={item} onOpen={() => openAlpi()} />)}
          </section>
        ) : null}
        {busy ? (
          <div className={styles.busy} role="status">
            <span className={styles.lineIcon}><Icon name="refresh" /></span>
            <span className={styles.lineLabel}>{busy}</span>
          </div>
        ) : null}
        {model.update ? (
          <div className={styles.update}>
            <span className={styles.lineIcon} data-tone="success"><Icon name="download" /></span>
            <span className={styles.updateText}>{model.update.text}</span>
            <Button size="sm" variant="secondary" loading={model.update.busy} onClick={() => call("restart_to_update")}>
              Restart to update
            </Button>
          </div>
        ) : null}
        <footer className={styles.foot}>
          <Button size="sm" variant="secondary" onClick={() => openAlpi()}>Open alpi</Button>
          <span className={styles.spacer} />
          {model.bell ? (
            <IconBtn size="sm" aria-label={model.bellLabel} onClick={() => call("open_notifications")}>
              <span className={styles.bellWrap}>
                <Icon name={ICON_ROLES.notifications} size="sm" />
                {model.unread > 0 ? <span className={styles.bellDot} aria-hidden /> : null}
              </span>
            </IconBtn>
          ) : null}
          <IconBtn size="sm" aria-label="Settings" onClick={() => call("open_settings")}>
            <Icon name={ICON_ROLES.settings} size="sm" />
          </IconBtn>
          <IconBtn size="sm" aria-label="Quit alpi" onClick={() => call("quit_app")}>
            <Icon name="power" size="sm" />
          </IconBtn>
        </footer>
      </main>
    </div>
  );
}

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { TWIN } from "../lib/brandMark.js";
import { ICON_ROLES } from "../../../common/iconRoles.mjs";
import { Button, Fold, Icon, IconBtn } from "../primitives/index.js";
import { nameVars } from "../lib/nameVars.js";
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
      <span className={styles.lineIcon}><Icon name={item.icon} /></span>
      <span className={styles.lineLabel}>{item.label}</span>
      <span className={styles.lineValue}>{item.value}</span>
      <span className={styles.chev}><Icon name="chevron-right" size="sm" /></span>
    </button>
  );
}

const HEAD_MARK = { needs: "needs", running: "working", failing: "failed", offline: "offline", starting: "busy", connecting: "busy" };

const whereOf = (row) => [row.name, row.connection, row.meta].filter(Boolean).join(" · ");

function RowBody({ row, mark, time }) {
  const live = mark !== "idle";
  const tail = [row.connection, row.meta].filter(Boolean).join(" · ");
  return (
    <>
      <span className={styles.mark}>
        <Fold shape={row.shape} color={row.accent || undefined} size={24} state={mark} still={!live} seed={row.key} />
      </span>
      <span className={styles.text}>
        <span className={styles.who}>
          <span className={styles.whoText}>
            <span className={`ds-name ${styles.name}`} style={nameVars(row.accent) ?? undefined}>{row.name}</span>
            {tail ? <span className={styles.meta}>{` · ${tail}`}</span> : null}
          </span>
          {time ? <span className={`tnum ${styles.time}`}>{time}</span> : null}
        </span>
        <span className={styles.rowTitle} title={row.title}>{row.title}</span>
      </span>
    </>
  );
}

function NeedsRow({ row, onReview }) {
  return (
    <li className={styles.row} data-kind={row.kind}>
      <span className={styles.rowMain} onClick={() => onReview(row)}>
        <RowBody row={row} mark="needs" />
      </span>
      <Button size="sm" variant="secondary" aria-label={`Review: ${row.title}, ${whereOf(row)}`} onClick={() => onReview(row)}>
        Review
      </Button>
    </li>
  );
}

function NextRow({ row, onOpen }) {
  return (
    <li className={styles.row} data-kind="next">
      <button type="button" className={styles.rowMain} onClick={() => onOpen(row)} aria-label={`${row.title}, ${whereOf(row)}, ${row.when}. Open schedule`}>
        <RowBody row={row} mark="idle" time={row.when} />
      </button>
    </li>
  );
}

function RunRow({ row, onOpen }) {
  return (
    <li className={styles.row} data-kind="running">
      <button type="button" className={styles.rowMain} onClick={() => onOpen(row)} aria-label={`${row.title}, ${whereOf(row)} · running${row.elapsed ? `, ${row.elapsed}` : ""}. Open`}>
        <RowBody row={row} mark="working" time={row.elapsed} />
      </button>
    </li>
  );
}

function Section({ label, children }) {
  return (
    <section className={styles.section} aria-label={label}>
      <p className={styles.sectionLabel}>{label}</p>
      {children}
    </section>
  );
}

function MoreLine({ n, onOpen }) {
  return (
    <button type="button" className={styles.line} onClick={onOpen}>
      <span className={styles.lineLabel}>{n} more · Open alpi</span>
      <span className={styles.chev}><Icon name="chevron-right" size="sm" /></span>
    </button>
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
          <Fold shape={TWIN} size={40} state={HEAD_MARK[state] ?? "idle"} seed="tray-head" />
          <div className={styles.headText}>
            <h1 className={styles.title} aria-live="polite">{title}</h1>
            <p className={styles.sub}>{sub}</p>
          </div>
        </header>
        {model.start && !starting ? (
          <div className={styles.start}>
            <Button variant="primary" fullWidth onClick={start}>Start alpi</Button>
          </div>
        ) : null}
        {model.rows.length > 0 ? (
          <Section label="Needs you">
            <ul className={styles.list}>
              {model.rows.map((row) => <NeedsRow key={row.key} row={row} onReview={review} />)}
            </ul>
            {model.more > 0 ? <MoreLine n={model.more} onOpen={() => openAlpi()} /> : null}
          </Section>
        ) : null}
        {model.failing ? (
          <button type="button" className={styles.banner} data-tone="danger" onClick={() => openAlpi()} aria-label={`${model.failing.title}${model.failing.detail ? `, ${model.failing.detail}` : ""}. Open alpi`}>
            <span className={styles.bannerIcon}><Icon name="triangle-alert" size="md" /></span>
            <span className={styles.bannerText}>
              <span className={styles.bannerTitle}>{model.failing.title}</span>
              {model.failing.detail ? <span className={styles.bannerDetail}>{model.failing.detail}</span> : null}
            </span>
            <span className={styles.chev}><Icon name="chevron-right" size="sm" /></span>
          </button>
        ) : null}
        {model.runs.length > 0 ? (
          <Section label="Running">
            <ul className={styles.list}>
              {model.runs.map((row) => <RunRow key={row.key} row={row} onOpen={review} />)}
            </ul>
            {model.runsMore > 0 ? <MoreLine n={model.runsMore} onOpen={() => openAlpi()} /> : null}
          </Section>
        ) : null}
        {model.nextGroups.map((group) => (
          <Section key={group.day} label={group.day}>
            <ul className={styles.list}>
              {group.rows.map((row) => <NextRow key={row.key} row={row} onOpen={review} />)}
            </ul>
          </Section>
        ))}
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
          <div className={styles.banner} data-tone="success">
            <span className={styles.bannerIcon}><Icon name="download" size="md" /></span>
            <span className={styles.bannerText}>
              <span className={styles.updateText}>{model.update.text}</span>
            </span>
            <Button size="sm" variant="secondary" aria-label="Restart to update" loading={model.update.busy} onClick={() => call("restart_to_update")}>
              Restart
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

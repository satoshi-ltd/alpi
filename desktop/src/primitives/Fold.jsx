import { Fragment, useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import { followPointer } from "../lib/gaze.js";
import { useWindowFocus } from "../lib/windowFocus.js";
import { shapeOf, TWIN_SHAPE, WORKGROUP_SHAPE } from "../../../common/shapes.mjs";
import { WG_ALPHA, WG_CELLS, WG_CENTRES, WG_DANGER, WG_FRONTAL, WG_ORDER, WG_OUTWARD, WG_POP, WG_RING, WG_STILLS, WG_TURNS } from "../../../common/workgroupMark.mjs";
import { WG_CSS } from "../lib/workgroupMotion.js";
import { currentCell, workgroupGap } from "../../../common/workgroupMarkState.mjs";
import { BODY, EYE_SPLINE, MARK_SIZES, MOTION_CSS, MOTION_MIN, SEQUENCE, SHAPES, SMALL, STILL, TURN, TURN_CSS } from "../../../common/agentMarks.mjs";
import { eyePair, eyePath as pathOf } from "../../../common/markEyes.mjs";
import { markTones } from "../../../common/markTone.mjs";
import { nameTone } from "../../../common/name.mjs";
import { palettes } from "../../../common/tokens.mjs";
import styles from "./Fold.module.css";

const BASE = "var(--c, var(--ink-3))";
const EYE = "var(--mark-eye)";
const BODY_TONE = "var(--mark-body)";

const POINTER_TURN = /\.vt:has\(\.vt-q\d:hover\) \.vt-held\{[^}]*\}/g;

let motionInjected = false;
function ensureMotion() {
  if (motionInjected || typeof document === "undefined") return;
  const el = document.createElement("style");
  el.setAttribute("data-agent-marks", "");
  el.textContent = MOTION_CSS + TURN_CSS.replace(POINTER_TURN, "") + WG_CSS;
  document.head.appendChild(el);
  motionInjected = true;
}

const FLAT = ["paused", "offline"];
const GAZE_TURN_Y = 21.6;
const GAZE_TURN_X = 14.4;
const GAZE_EYE_X = 6;
const GAZE_EYE_Y = 4;
const EASE = "320ms cubic-bezier(0.3, 0.7, 0.4, 1)";

function rotation([ry, rx, rz]) {
  return `rotateY(${ry}deg) rotateX(${rx}deg) rotateZ(${rz}deg)`;
}

function parallax([ry, rx]) {
  const sy = Math.sin((ry * Math.PI) / 180);
  const sx = Math.sin((rx * Math.PI) / 180);
  return `translate(${TURN.slide[0] * sy}px, ${-TURN.slide[1] * sx}px) scale(${1 - TURN.squeeze * Math.abs(sy)}, ${1 - TURN.squeeze * Math.abs(sx)})`;
}

function stillPose(state, px) {
  const pose = TURN.still[state];
  if (!pose) return [0, 0, 0];
  const k = px > MARK_SIZES.row ? 1 : TURN.smallTurn;
  return pose.map((a) => a * k);
}

function delayFor(seed) {
  let h = 0;
  for (const ch of String(seed)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return -(h % 96) / 10;
}

const REDUCE_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeReducedMotion(fn) {
  const query = typeof window === "undefined" ? null : window.matchMedia?.(REDUCE_QUERY);
  query?.addEventListener?.("change", fn);
  return () => query?.removeEventListener?.("change", fn);
}

const prefersReducedMotion = () => (typeof window === "undefined" ? false : !!window.matchMedia?.(REDUCE_QUERY).matches);
const serverReducedMotion = () => false;

function useReducedMotion() {
  return useSyncExternalStore(subscribeReducedMotion, prefersReducedMotion, serverReducedMotion);
}

function Eyes({ spec, size, state, still, fill, follow, seed }) {
  const seq = still ? null : SEQUENCE[state];
  const drawn = useMemo(() => {
    const rest = eyePair(spec, size, STILL[state] ?? STILL.idle).map(pathOf);
    if (!seq) return { rest };
    const frames = seq.keys.map((key) => eyePair(spec, size, key).map(pathOf));
    return {
      rest,
      values: [0, 1].map((side) => frames.map((pair) => pair[side]).join(";")),
      times: seq.keys.map((key) => key[0]).join(";"),
      splines: seq.keys.slice(1).map(() => EYE_SPLINE).join(";"),
    };
  }, [spec, size, state, seq]);
  const look = follow ? { transform: `translate(calc(var(--gx, 0) * ${GAZE_EYE_X}px), calc(var(--gy, 0) * ${GAZE_EYE_Y}px))` } : undefined;
  if (!drawn.values) return <g style={look}>{drawn.rest.map((d, side) => <path key={side} data-eye="" d={d} fill={fill} />)}</g>;
  const begin = `${delayFor(seed)}s`;
  return (
    <g style={look}>
      {drawn.values.map((values, side) => (
        <path key={`${state}-${side}`} data-eye="" d={drawn.rest[side]} fill={fill}>
          <animate attributeName="d" values={values} keyTimes={drawn.times} dur={`${seq.dur}s`} begin={begin} repeatCount="indefinite" calcMode="spline" keySplines={drawn.splines} />
        </path>
      ))}
    </g>
  );
}

function stateFrom({ state, pulse, outlined, unfolded }) {
  if (state) return state;
  if (outlined) return "needs";
  if (unfolded) return "paused";
  if (pulse) return "working";
  return "idle";
}

function Signature({ spec, state }) {
  if (spec.balls && (state === "busy" || state === "working")) {
    const working = state === "working";
    const half = working ? 0.6 : 1.4;
    return spec.balls.map(({ x, y, r }, k) => (
      <circle key={k} className={`am-a am-sig-${working ? "blink" : "pulse"}`} cx={x} cy={y} r={r * 0.46} fill={EYE} opacity="0"
        style={{ transformOrigin: `${x}px ${y}px`, animationDelay: `calc(var(--d, 0s) + ${k * half}s)` }} />
    ));
  }
  return null;
}

function Mark({ id, color, px, state, seed, watch, still, className, style }) {
  const alpi = id === TWIN_SHAPE;
  const name = alpi ? `alpi-twin${px < 24 ? "-small" : ""}` : SHAPES[id] ? id : "round";
  const spec = SHAPES[name];
  const tones = alpi ? null : markTones(color);
  const fill = alpi ? "var(--accent)" : tones ? BODY_TONE : color || BASE;
  const reduced = useReducedMotion();
  const awake = useWindowFocus();
  const animate = awake && !still && !reduced && px >= MOTION_MIN && (state !== "idle" || px >= SMALL);
  const turning = !FLAT.includes(state);
  const follow = awake && !still && !!watch && !reduced && turning && px >= MARK_SIZES.hero;
  const gazeRef = useRef(null);
  useEffect(() => (follow ? followPointer(gazeRef.current, { look: true }) : undefined), [follow]);
  if (animate) ensureMotion();
  const pose = turning && !follow ? stillPose(state, px) : [0, 0, 0];
  const liveTurn = animate && turning && !follow && TURN.live.includes(state);
  let inner;
  if (state === "paused") {
    const thin = px < SMALL;
    const width = thin ? 5.5 : 3.6;
    inner = (
      <>
        <path d={spec.d} fill="none" stroke="var(--ink-3)" strokeWidth={width} strokeDasharray={thin ? "8 6" : "6.5 5"} strokeLinecap="round" />
        <Eyes spec={spec} size={px} state={state} still fill="var(--ink-3)" />
      </>
    );
  } else if (state === "offline") {
    inner = <path data-body="" d={spec.d} fill={fill} opacity={0.3} />;
  } else {
    inner = (
      <>
        <path data-body="" d={spec.d} fill={fill} />
        <g className={liveTurn ? `vt-a vt-eyes-${state}` : undefined} style={{ transformOrigin: `${spec.eyeX}px ${spec.eyeY}px`, transform: parallax(pose), transition: liveTurn ? undefined : `transform ${EASE}` }}>
          <Eyes spec={spec} size={px} state={state} still={!animate} fill={EYE} follow={follow} seed={seed ?? id} />
        </g>
        {animate ? <Signature spec={spec} state={state} /> : null}
      </>
    );
  }
  if (animate && BODY[state]) {
    inner = (
      <g className={`am-a am-body-${BODY[state]}`} style={{ "--s": spec.stretch, "--w": spec.wobble, transformOrigin: `50px ${spec.originY}px` }}>
        {inner}
      </g>
    );
  }
  const slot = [styles.slot, tones ? styles.toned : null, className].filter(Boolean).join(" ");
  const toneVars = tones ? { "--mark-light": tones.light, "--mark-dark": tones.dark } : null;
  return (
    <span className={slot} style={{ width: px, height: px, perspective: `${px * TURN.depth}px`, ...toneVars, ...style }} aria-hidden data-shape={id} data-mark={name} data-state={state} data-live={animate ? "" : undefined} data-watch={follow ? "" : undefined}>
      <span ref={gazeRef} style={follow ? { display: "block", transformStyle: "preserve-3d", transformOrigin: "50% 55%", transform: `rotateY(calc(var(--gx, 0) * ${GAZE_TURN_Y}deg)) rotateX(calc(var(--gy, 0) * ${-GAZE_TURN_X}deg))` } : { display: "block" }}>
      <svg
        className={liveTurn ? `vt-a vt-turn-${state}` : undefined}
        viewBox="0 0 100 100"
        width={px}
        height={px}
        style={{
          display: "block",
          overflow: "visible",
          flexShrink: 0,
          "--d": `${delayFor(seed ?? id)}s`,
          transformOrigin: "50% 55%",
          transform: rotation(pose),
          transition: liveTurn ? undefined : `transform ${EASE}`,
        }}
      >
        {inner}
      </svg>
      </span>
    </span>
  );
}

const NEUTRAL = "var(--ink-3)";
const HUB = "var(--accent)";
const LIT = "var(--wg-lit)";
const DANGER = `var(--c-danger, ${WG_DANGER})`;
const GAPS = Object.keys(WG_CELLS).map(Number);

function cellsFor(px) {
  const want = workgroupGap(px);
  const gap = GAPS.reduce((best, g) => (Math.abs(g - want) < Math.abs(best - want) ? g : best), GAPS[0]);
  return WG_CELLS[String(gap.toFixed(1))] ?? WG_CELLS[String(gap)];
}

function turnKey(state, cell) {
  if (state === "running") return cell ? `running-${cell}` : "idle";
  if (state === "failed") return `failed-${cell || "top"}`;
  if (state === "needs" || state === "queued") return state;
  return "idle";
}

function dashed(d, colour, thin) {
  return (
    <path d={d} fill="none" stroke={colour}
      strokeWidth={thin ? 5.5 : 3.6} strokeDasharray={thin ? "8 6" : "6.5 5"} strokeLinecap="round" />
  );
}

function Popped({ d, name, colour, live }) {
  const [cx, cy] = WG_CENTRES[name];
  const [ox, oy] = WG_OUTWARD[name];
  if (!live) {
    return <g transform={`translate(${(cx + ox).toFixed(1)} ${(cy + oy).toFixed(1)}) scale(${WG_POP[1]}) translate(${-cx} ${-cy})`}><path d={d} fill={colour} /></g>;
  }
  return (
    <g className="am-a am-wg-pop" style={{ transformOrigin: `${cx}px ${cy}px`, "--ox": `${ox.toFixed(2)}px`, "--oy": `${oy.toFixed(2)}px` }}>
      <path d={d} fill={colour} />
    </g>
  );
}

function ring(own, d, colour, thin) {
  return <path {...own} d={d} fill="none" stroke={colour} strokeWidth={thin ? WG_RING[0] : WG_RING[1]} />;
}

function paintCell({ name, i, d, thin, pop, lead, state, phase, cell, hub, live }) {
  const own = { "data-cell": name };
  const faint = <path {...own} d={d} fill={NEUTRAL} fillOpacity={WG_ALPHA.faint} />;
  if (state === "paused") return <g {...own}>{dashed(d, NEUTRAL, thin)}</g>;
  if (state === "queued") return ring(own, d, NEUTRAL, thin);
  if (state === "offline") return <path {...own} d={d} fill={NEUTRAL} fillOpacity={WG_ALPHA.offline} />;
  if (state === "failed") return name === cell ? <path {...own} data-lead="" d={d} fill={DANGER} /> : faint;
  if (state === "needs") {
    if (name !== cell) return <path {...own} d={d} fill={NEUTRAL} />;
    return pop ? <g {...own} data-lead=""><Popped d={d} name={name} colour={hub} live={live} /></g> : <path {...own} data-lead="" d={d} fill={hub} />;
  }
  if (state === "running" && phase) {
    if (i < lead) return faint;
    if (i === lead) return <path {...own} data-lead="" d={d} fill={hub} className={live ? "am-a am-wg-fill" : undefined} />;
    return ring(own, d, NEUTRAL, thin);
  }
  if (state === "running") {
    const top = name === "top";
    return (
      <path {...own} d={d} fill={hub} fillOpacity={top ? undefined : WG_ALPHA.chase}
        className={live ? "am-a am-wg-chase" : undefined}
        style={live ? { animationDelay: `calc(var(--d, 0s) + ${(0.8 * i).toFixed(1)}s)` } : undefined} />
    );
  }
  return <path {...own} d={d} fill={NEUTRAL} />;
}

export function litTones(accent) {
  const light = nameTone(accent, palettes.light.bgPane);
  const dark = nameTone(accent, palettes.dark.bgPane);
  return light && dark ? { "--wg-lit-light": light, "--wg-lit-dark": dark } : null;
}

function honeycombCells({ px, state, phase, cell, hub, live }) {
  const paths = cellsFor(px);
  const thin = px < SMALL;
  const pop = px > MARK_SIZES.row;
  const lead = WG_ORDER.indexOf(cell);
  return WG_ORDER.map((name, i) => <Fragment key={name}>{paintCell({ name, i, d: paths[name], thin, pop, lead, state, phase, cell, hub, live })}</Fragment>);
}

function Honeycomb({ color, px, state, phase, cell: given, seed, still, className, style }) {
  const reduced = useReducedMotion();
  const awake = useWindowFocus();
  const live = awake && !still && !reduced && px > MARK_SIZES.row;
  if (live) ensureMotion();
  const tones = litTones(color);
  const hub = tones ? LIT : color || HUB;
  const cell = given ?? currentCell(phase) ?? (state === "running" ? null : "top");
  let inner = honeycombCells({ px, state, phase: cell ? phase : null, cell, hub, live });
  if (state === "failed" && live) inner = <g className="am-a am-wg-shiver">{inner}</g>;
  const key = turnKey(state, phase ? cell : null);
  const frontal = reduced || WG_FRONTAL.includes(state);
  const k = px > MARK_SIZES.row ? 1 : TURN.smallTurn;
  const pose = frontal ? [0, 0, 0] : (WG_STILLS[key] ?? WG_STILLS.idle).map((a) => a * k);
  const moving = live && !frontal && !!WG_TURNS[key];
  const slot = [styles.slot, tones ? styles.lit : null, className].filter(Boolean).join(" ");
  return (
    <span
      className={slot}
      style={{ width: px, height: px, perspective: `${Math.round(px * TURN.depth)}px`, "--d": live ? `${delayFor(`${seed ?? color ?? ""}wg`)}s` : undefined, ...tones, ...style }}
      aria-hidden
      data-shape={WORKGROUP_SHAPE}
      data-mark="soft-honeycomb"
      data-state={state}
      data-cell={cell ?? undefined}
    >
      <svg
        className={moving ? `vt-a vt-wg-${key}` : undefined}
        viewBox="0 0 100 100"
        width={px}
        height={px}
        style={{ display: "block", overflow: "visible", flexShrink: 0, transformOrigin: "50% 50%", transform: rotation(pose) }}
      >
        {inner}
      </svg>
    </span>
  );
}

function workgroupState({ state, pulse, outlined, unfolded }) {
  if (state) return state;
  if (outlined || unfolded) return "paused";
  if (pulse) return "running";
  return "idle";
}

export default function Fold({ shape, color, size, pulse = false, outlined = false, unfolded = false, state, phase, cell, seed, watch = false, still = false, className = "", style }) {
  const px = typeof size === "number" ? size : size === "md" ? MARK_SIZES.header : MARK_SIZES[size] ?? MARK_SIZES.row;
  const id = shapeOf(shape);
  if (id === WORKGROUP_SHAPE) {
    return <Honeycomb color={color} px={px} state={workgroupState({ state, pulse, outlined, unfolded })} phase={phase} cell={cell} seed={seed} still={still} className={className} style={style} />;
  }
  return <Mark id={id} color={color} px={px} state={stateFrom({ state, pulse, outlined, unfolded })} seed={seed} watch={watch} still={still} className={className} style={style} />;
}

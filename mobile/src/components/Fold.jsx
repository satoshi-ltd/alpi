import { useEffect, useMemo } from 'react';
import { View } from 'react-native';
import Animated, { cancelAnimation, Easing, useAnimatedProps, useAnimatedStyle, useSharedValue, withRepeat, withTiming } from 'react-native-reanimated';
import Svg, { G, Path } from 'react-native-svg';

import { shapeOf, WORKGROUP_SHAPE } from '../../../common/shapes.mjs';
import { MARK_SIZES } from '../../../common/agentMarks.mjs';
import { WG_CENTRES, WG_DANGER, WG_OUTWARD, WG_POP } from '../../../common/workgroupMark.mjs';
import { animates, delayFor, eyesPath, eyeTrack, FLAT_STATES, loopSeconds, markFill, markName, markRotation, OFFLINE_OPACITY, OUTLINED_STATES, parallax, sampleTrack, SHAPES, stateFrom, stillEyes, stillPose, TURN_TRACKS, turnsLive } from '../lib/agentMark';
import { cellPaint, CHASE_TRACK, cellPaths, FILL_TRACK, parsePhase, turnKey, WG_ORDER, wgLive, wgPose, wgState, wgTrack } from '../lib/workgroupMark';
import { useAppActive } from '../lib/appActive';
import { useReduceMotion } from '../lib/reduceMotion';
import { useTheme } from '../theme/ThemeContext';
import { nameTone } from '../../../common/name.mjs';

const AnimatedPath = Animated.createAnimatedComponent(Path);
const NO_SHIFT = [0, 0, 1, 1];

const pxFor = (size) => (typeof size === 'number' ? size : size === 'md' ? MARK_SIZES.header : MARK_SIZES[size] ?? MARK_SIZES.row);

function useClock(seconds, offset) {
  const clock = useSharedValue(offset);
  useEffect(() => {
    if (!seconds) return undefined;
    clock.value = offset;
    clock.value = withRepeat(withTiming(offset + seconds, { duration: seconds * 1000, easing: Easing.linear }), -1, false);
    return () => cancelAnimation(clock);
  }, [clock, seconds, offset]);
  return clock;
}

function Slot({ px, children }) {
  return (
    <View style={{ width: px, height: px, flexShrink: 0, overflow: 'visible' }} pointerEvents="none">
      {children}
    </View>
  );
}

const tagsOf = (id, name, state) => ({ 'data-shape': id, 'data-mark': name, 'data-state': state });

function Turned({ px, pose, children }) {
  return <View style={{ width: px, height: px, transformOrigin: ['50%', '55%', 0], transform: markRotation(pose, px) }}>{children}</View>;
}

function StillMark({ spec, px, state, fill, neutral, eye, tags }) {
  const pose = useMemo(() => stillPose(state, px), [state, px]);
  const eyes = useMemo(() => {
    if (OUTLINED_STATES.includes(state) || state === 'offline') return null;
    return eyesPath(stillEyes(spec, px, state), spec, parallax(pose));
  }, [spec, px, state, pose]);
  const thin = px < 32;
  let inner;
  if (OUTLINED_STATES.includes(state)) {
    inner = (
      <>
        <Path d={spec.d} fill="none" stroke={neutral} strokeWidth={thin ? 5.5 : 3.6} strokeDasharray={thin ? '8 6' : '6.5 5'} strokeLinecap="round" />
        <Path testID="mark-eyes" d={eyesPath(stillEyes(spec, px, state), spec, NO_SHIFT)} fill={neutral} />
      </>
    );
  } else if (state === 'offline') {
    inner = <Path testID="mark-body" d={spec.d} fill={fill} fillOpacity={OFFLINE_OPACITY} />;
  } else {
    inner = (
      <>
        <Path testID="mark-body" d={spec.d} fill={fill} />
        <Path testID="mark-eyes" d={eyes} fill={eye} />
      </>
    );
  }
  return (
    <Turned px={px} pose={pose}>
      <Svg width={px} height={px} viewBox="0 0 100 100" style={{ overflow: 'visible' }} {...tags}>{inner}</Svg>
    </Turned>
  );
}

function LiveMark({ spec, px, state, fill, eye, seed, tags }) {
  const track = useMemo(() => eyeTrack(spec, px, state), [spec, px, state]);
  const turn = turnsLive(state, px) ? TURN_TRACKS[state] : null;
  const held = stillPose(state, px);
  const seconds = loopSeconds(track.dur, turn?.dur);
  const clock = useClock(seconds, delayFor(seed));
  const style = useAnimatedStyle(() => {
    const pose = turn ? sampleTrack(turn, clock.value) : held;
    return { transform: markRotation(pose, px) };
  });
  const props = useAnimatedProps(() => {
    const pose = turn ? sampleTrack(turn, clock.value) : held;
    return { d: eyesPath(sampleTrack(track, clock.value), spec, parallax(pose)) };
  });
  return (
    <Animated.View style={[{ width: px, height: px, transformOrigin: ['50%', '55%', 0] }, style]}>
      <Svg width={px} height={px} viewBox="0 0 100 100" style={{ overflow: 'visible' }} {...tags}>
        <Path testID="mark-body" d={spec.d} fill={fill} />
        <AnimatedPath testID="mark-eyes" animatedProps={props} fill={eye} />
      </Svg>
    </Animated.View>
  );
}

function ProfileMark({ id, color, px, state, seed, still }) {
  const { colors, mode } = useTheme();
  const reduced = useReduceMotion();
  const awake = useAppActive();
  const name = markName(id, px);
  const spec = SHAPES[name];
  const fill = markFill({ id, color, mode, fallback: colors.ink3 });
  const live = awake && !still && animates(state, px, reduced) && !FLAT_STATES.includes(state);
  const tags = tagsOf(id, name, state);
  return (
    <Slot px={px}>
      {live
        ? <LiveMark spec={spec} px={px} state={state} fill={fill} eye={colors.markEye} seed={seed ?? id} tags={tags} />
        : <StillMark spec={spec} px={px} state={state} fill={fill} neutral={colors.ink3} eye={colors.markEye} tags={tags} />}
    </Slot>
  );
}

function LiveCell({ d, paint, clock, track }) {
  const props = useAnimatedProps(() => ({ fillOpacity: sampleTrack(track, clock.value - (paint.lag ?? 0))[0] }));
  return <AnimatedPath d={d} fill={paint.fill} animatedProps={props} />;
}

function Cell({ d, name, paint, clock }) {
  if (paint.track && clock) return <LiveCell d={d} paint={paint} clock={clock} track={paint.track === 'fill' ? FILL_TRACK : CHASE_TRACK} />;
  const { pop, track, lag, ...attrs } = paint;
  const path = <Path d={d} {...attrs} />;
  if (!pop) return path;
  const [cx, cy] = WG_CENTRES[name];
  const [ox, oy] = WG_OUTWARD[name];
  return <G transform={`translate(${cx + ox} ${cy + oy}) scale(${WG_POP[1]}) translate(${-cx} ${-cy})`}>{path}</G>;
}

function Cells({ px, state, phase, cell, hub, neutral, danger, clock }) {
  const paths = cellPaths(px);
  return WG_ORDER.map((name, index) => (
    <Cell key={name} d={paths[name]} name={name} clock={clock} paint={cellPaint({ name, index, state, phase, cell, hub, neutral, danger, px })} />
  ));
}

function LiveHoneycomb({ px, track, seed, tags, ...cells }) {
  const clock = useClock(loopSeconds(track.dur, 2.4), delayFor(`${seed}wg`));
  const style = useAnimatedStyle(() => ({ transform: markRotation(sampleTrack(track, clock.value), px) }));
  return (
    <Animated.View style={[{ width: px, height: px, transformOrigin: ['50%', '50%', 0] }, style]}>
      <Svg width={px} height={px} viewBox="0 0 100 100" style={{ overflow: 'visible' }} {...tags}>
        <Cells px={px} clock={clock} {...cells} />
      </Svg>
    </Animated.View>
  );
}

function Honeycomb({ color, px, state, phase, cell, seed, still }) {
  const { colors } = useTheme();
  const reduced = useReduceMotion();
  const awake = useAppActive();
  const hub = /^#[0-9a-f]{6}$/i.test(color ?? '') ? nameTone(color, colors.bg) ?? color : colors.accent;
  const run = parsePhase(phase);
  const key = turnKey(state, run, cell);
  const cells = { state, phase: run, cell, hub, neutral: colors.ink3, danger: colors.danger ?? WG_DANGER };
  const track = awake && !still && wgLive(state, key, px, reduced) ? wgTrack(key) : null;
  const tags = tagsOf(WORKGROUP_SHAPE, 'soft-honeycomb', state);
  return (
    <Slot px={px}>
      {track ? (
        <LiveHoneycomb px={px} track={track} seed={seed ?? hub} tags={tags} {...cells} />
      ) : (
        <View style={{ width: px, height: px, transformOrigin: ['50%', '50%', 0], transform: markRotation(wgPose(state, key, px), px) }}>
          <Svg width={px} height={px} viewBox="0 0 100 100" style={{ overflow: 'visible' }} {...tags}>
            <Cells px={px} {...cells} />
          </Svg>
        </View>
      )}
    </Slot>
  );
}

export function Fold({ shape, color, size, pulse = false, outlined = false, unfolded = false, still = false, state, seed, phase, cell }) {
  const px = pxFor(size);
  const id = shapeOf(shape);
  if (id === WORKGROUP_SHAPE) {
    return <Honeycomb color={color} px={px} state={wgState({ state, pulse, outlined, unfolded })} phase={phase} cell={cell} seed={seed} still={still} />;
  }
  return <ProfileMark id={id} color={color} px={px} state={stateFrom({ state, pulse, outlined, unfolded })} seed={seed} still={still} />;
}

import React from 'react';
import * as RN from 'react-native';

export const state = { reducedMotion: false, keyboardHeight: 0, timings: [], hold: false, pending: [] };

const flat = (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean));

const plain = ({ children, style, ...p }) => React.createElement('div', { ...p, 'data-style': JSON.stringify(flat(style)) }, children);

function hostFor(tag) {
  try {
    return RN[tag] ?? plain;
  } catch {
    return plain;
  }
}

function wrap(tag) {
  return function AnimatedHost({ entering, exiting, layout, style, ...props }) {
    const host = hostFor(tag);
    return React.createElement(host, {
      ...props,
      style: flat(style),
      'data-entering': entering ? String(entering.label ?? 'anim') : undefined,
    });
  };
}

function builder(label) {
  const b = { label, ms: undefined };
  b.duration = (ms) => ({ ...b, ms, label: `${label}:${ms}` });
  b.reduceMotion = () => b;
  return b;
}

const Animated = {
  View: wrap('View'),
  Text: wrap('Text'),
  ScrollView: wrap('ScrollView'),
  createAnimatedComponent: (C) => C,
};

export default Animated;
export const FadeIn = builder('FadeIn');
export const FadeInDown = builder('FadeInDown');
export const FadeOut = builder('FadeOut');
export const Easing = { bezier: () => 'bezier', inOut: (e) => e, ease: 'ease', linear: 'linear' };
export const ReduceMotion = { System: 'system', Always: 'always', Never: 'never' };
export const useReducedMotion = () => state.reducedMotion;
export const useAnimatedKeyboard = () => ({ height: { value: state.keyboardHeight }, state: { value: 0 } });
export const useAnimatedStyle = (fn) => fn();
export const useSharedValue = (initial) => React.useRef({ value: initial }).current;
export const useDerivedValue = (fn) => ({ value: fn() });
export const withTiming = (v, config, done) => {
  state.timings.push({ to: v, duration: config?.duration });
  if (done && state.hold) state.pending.push(done);
  else done?.(true);
  return v;
};
export function finishTimings(finished = true) {
  for (const done of state.pending.splice(0)) done(finished);
}
export const withRepeat = (v) => v;
export const withSequence = (...v) => v[v.length - 1];
export const cancelAnimation = () => {};
export const runOnJS = (fn) => fn;
export const scheduleOnRN = (fn, ...args) => fn(...args);

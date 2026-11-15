import { describe, expect, it } from 'vitest';

import { EXPRESSIONS, SEQUENCE, SHAPES, STILL, TURN } from '../../../common/agentMarks.mjs';
import { animates, delayFor, ease, eyePair, eyesPath, eyeTrack, loopSeconds, markName, parallax, sampleTrack, stateFrom, stillPose, TURN_TRACKS, turnsLive } from './agentMark';
import { cellPaths, currentCell, parsePhase, turnKey, wgPose } from './workgroupMark';

describe('agentMark', () => {
  it('draws every shape by name, a legacy id as the round and the default profile as Twin', () => {
    for (const shape of Object.keys(SHAPES).filter((n) => !n.startsWith('alpi-'))) expect(markName(shape, 40)).toBe(shape);
    for (const legacy of ['shield', 'rocket', 'crown', 'alpaca']) expect(markName(legacy, 40)).toBe('round');
    expect(markName('twin', 23)).toBe('alpi-twin-small');
    expect(markName('twin', 24)).toBe('alpi-twin');
    expect(markName('nope', 40)).toBe('round');
  });

  it('derives the state from the legacy flags', () => {
    expect(stateFrom({ state: 'done' })).toBe('done');
    expect(stateFrom({ outlined: true, pulse: true })).toBe('needs');
    expect(stateFrom({ state: 'disabled' })).toBe('idle');
    expect(stateFrom({ unfolded: true })).toBe('paused');
    expect(stateFrom({ pulse: true })).toBe('working');
    expect(stateFrom({ state: 'bogus' })).toBe('idle');
  });

  it('builds two eyes of 48 points each, one each side of the eye centre', () => {
    const spec = SHAPES.round;
    const flat = eyePair(spec, 72, STILL.idle);
    expect(flat).toHaveLength(EXPRESSIONS.rest.length * 4);
    const xs = (from, to) => flat.slice(from, to).filter((_, i) => i % 2 === 0);
    expect(Math.max(...xs(0, 96))).toBeLessThan(spec.eyeX);
    expect(Math.min(...xs(96, 192))).toBeGreaterThan(spec.eyeX);
  });

  it('writes the eyes as two closed subpaths', () => {
    const d = eyesPath(eyePair(SHAPES.bell, 40, STILL.done), SHAPES.bell, [0, 0, 1, 1]);
    expect(d.match(/M/g)).toHaveLength(2);
    expect(d.match(/Z/g)).toHaveLength(2);
  });

  it('eases on the shared spline from 0 to 1, monotonically', () => {
    expect(ease(0)).toBe(0);
    expect(ease(1)).toBe(1);
    let last = 0;
    for (let x = 0.05; x < 1; x += 0.05) {
      expect(ease(x)).toBeGreaterThanOrEqual(last);
      last = ease(x);
    }
  });

  it('samples a track at its keys and loops it', () => {
    const track = eyeTrack(SHAPES.round, 40, 'busy');
    expect(track.dur).toBe(SEQUENCE.busy.dur);
    expect(sampleTrack(track, 0)).toEqual(track.values[0]);
    expect(sampleTrack(track, track.dur)).toEqual(track.values[0]);
    const mid = sampleTrack(track, track.dur * 0.23);
    expect(mid).toHaveLength(track.values[0].length);
  });

  it('reads a turn track for every live state from the shared turn css', () => {
    for (const state of TURN.live) {
      const track = TURN_TRACKS[state];
      expect(track.times[0]).toBe(0);
      expect(track.times[track.times.length - 1]).toBe(1);
      expect(track.values[0]).toHaveLength(3);
    }
    expect(TURN_TRACKS.idle.dur).toBe(9.6);
    expect(TURN_TRACKS.idle.values[0]).toEqual([24, 5, -3]);
  });

  it('loops eyes and turn on one clock long enough for both', () => {
    expect(loopSeconds(4.2, 2.8)).toBe(8.4);
    expect(loopSeconds(9.6, 9.6)).toBe(9.6);
    expect(loopSeconds(4.8, undefined)).toBe(4.8);
  });

  it('slides the eyes toward the turn', () => {
    const [tx, ty, sx, sy] = parallax([24, 5, -3]);
    expect(tx).toBeCloseTo(7.3, 1);
    expect(ty).toBeCloseTo(-1.1, 1);
    expect(sx).toBeCloseTo(0.87, 2);
    expect(sy).toBeCloseTo(0.972, 2);
  });

  it('holds a smaller angle at row size and none for flat states', () => {
    expect(stillPose('idle', 40)).toEqual(TURN.still.idle);
    expect(stillPose('idle', 20)).toEqual(TURN.still.idle.map((a) => a * TURN.smallTurn));
    expect(stillPose('paused', 72)).toEqual([0, 0, 0]);
  });

  it('animates only moving states at a size that shows them, never under reduced motion', () => {
    expect(animates('idle', 20, false)).toBe(false);
    expect(animates('idle', 40, false)).toBe(true);
    expect(animates('working', 20, false)).toBe(true);
    expect(animates('working', 14, false)).toBe(false);
    expect(animates('paused', 72, false)).toBe(false);
    expect(animates('busy', 72, true)).toBe(false);
    expect(turnsLive('busy', 20)).toBe(false);
    expect(turnsLive('busy', 28)).toBe(true);
  });

  it('staggers marks by seed', () => {
    expect(delayFor('a')).not.toBe(delayFor('b'));
    expect(delayFor('a')).toBe(delayFor('a'));
  });
});

describe('workgroupMark', () => {
  it('reads the run progress and picks the active cell', () => {
    expect(parsePhase('2/4')).toEqual([2, 4]);
    expect(parsePhase('0/0')).toBeNull();
    expect(parsePhase(null)).toBeNull();
    expect(parsePhase([])).toBeNull();
    expect(parsePhase([1, 0])).toBeNull();
    expect(parsePhase(['a', 3])).toBeNull();
    expect(parsePhase([5, 3])).toEqual([3, 3]);
    expect(currentCell(null)).toBeNull();
    expect(currentCell([])).toBeNull();
    expect(currentCell([1, 0])).toBeNull();
    expect(currentCell([0, 3])).toBe('left');
    expect(currentCell([1, 3])).toBe('top');
    expect(currentCell([3, 3])).toBe('right');
  });

  it('turns toward the active cell', () => {
    expect(turnKey('running', [3, 4], null)).toBe('running-right');
    expect(turnKey('running', null, null)).toBe('idle');
    expect(turnKey('failed', null, 'left')).toBe('failed-left');
    expect(wgPose('paused', 'idle', 40)).toEqual([0, 0, 0]);
  });

  it('opens the gap between cells at small sizes', () => {
    expect(cellPaths(14).top).not.toBe(cellPaths(72).top);
    expect(cellPaths(28).top).toBe(cellPaths(72).top);
  });
});

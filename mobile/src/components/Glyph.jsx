import { WORKGROUP_SHAPE } from '../../../common/shapes.mjs';
import { workgroupMark } from '../../../common/workgroupMarkState.mjs';
import { parsePhase } from '../lib/workgroupMark';
import { useTheme } from '../theme/ThemeContext';
import { Fold } from './Fold';

export function markState({ needsProvider = false, paused = false, offline = false, rowState = null, working = false, pending = false, unread = false, live = null }) {
  if (offline) return 'offline';
  if (paused) return 'paused';
  if (needsProvider) return 'needs';
  if (rowState === 'needs-you') return 'needs';
  if (live && live !== 'idle') return live;
  if (rowState === 'failed') return 'failed';
  if (rowState === 'working' || working || pending) return 'working';
  if (unread) return 'done';
  return 'idle';
}

export function workgroupGlyph({ workgroup = null, paused = false, offline = false, working = false, rowState = null, phase = null, phaseSlug = null }) {
  const [done, total] = parsePhase(phase) ?? [];
  const run = working || rowState === 'working' ? { phasesDone: done, phasesTotal: total, phase: phaseSlug } : null;
  return workgroupMark({
    workgroup: { ...workgroup, paused: paused || !!workgroup?.paused },
    run,
    task: rowState === 'failed' ? { state: 'error' } : null,
    offline,
  });
}

export function Glyph({ kind, color, shape, name, active = false, state = null, workgroup = null, needsProvider = false, working = false, paused = false, offline = false, rowState = null, pending = false, unread = false, phase = null, phaseSlug = null, size }) {
  const { colors } = useTheme();
  const tint = typeof color === 'string' && color.startsWith('#') ? color : colors.ink3;
  if (kind === 'workgroup') {
    const mark = workgroupGlyph({ workgroup, paused, offline, working, rowState, phase, phaseSlug });
    return <Fold shape={WORKGROUP_SHAPE} color={tint} size={size} state={mark.state} phase={mark.phase} seed={name} still={!active} />;
  }
  return <Fold shape={shape} color={tint} size={size} state={markState({ needsProvider, paused, offline, rowState, working, pending, unread, live: state })} seed={name} still={!active} />;
}

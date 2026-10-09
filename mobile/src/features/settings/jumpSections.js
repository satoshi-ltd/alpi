import { attentionItems } from '../../../../common/attention.mjs';

export const JUMP_SECTIONS = [
  { id: 'overview', label: 'Overview' },
  { id: 'usage', label: 'Usage' },
  { id: 'identity', label: 'Identity' },
  { id: 'service', label: 'Service' },
  { id: 'alp', label: 'ALP' },
  { id: 'schedule', label: 'Schedule' },
  { id: 'sandbox', label: 'Sandbox' },
  { id: 'voice', label: 'Voice' },
  { id: 'mcp', label: 'MCP' },
  { id: 'brain', label: 'Brain' },
  { id: 'storage', label: 'Storage' },
];

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

export function summaryRows(att) {
  const jobs = attentionItems(att, 'schedule').length;
  const files = attentionItems(att, 'memory').length;
  const skills = attentionItems(att, 'skills').length;
  return [
    jobs ? { id: 'schedule', text: `${plural(jobs, 'job', 'jobs')} failed`, section: 'schedule', label: 'Schedule' } : null,
    files ? { id: 'memory', text: `${plural(files, 'memory file', 'memory files')} at or over ${files === 1 ? 'its' : 'their'} limit`, section: 'brain', label: 'Brain' } : null,
    skills ? { id: 'skills', text: `${plural(skills, 'skill', 'skills')} to fix`, section: 'brain', label: 'Brain' } : null,
  ].filter(Boolean);
}

export function sectionAt(offsets, scrollY, slack = 12) {
  let current = JUMP_SECTIONS[0].id;
  for (const { id } of JUMP_SECTIONS) {
    const y = offsets[id];
    if (typeof y === 'number' && y <= scrollY + slack) current = id;
  }
  return current;
}

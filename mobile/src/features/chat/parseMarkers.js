import { classifyMessage, closeStatus } from '../../../../common/workgroupMarkers.mjs';

export {
  classifyMessage,
  closeStatus,
  parseDone,
  parseSkip,
  parseTaskOpen,
  parseWorking,
  validateTaskShape,
} from '../../../../common/workgroupMarkers.mjs';

export function buildTasks(messages, hubPubkey = null) {
  const tasks = [];
  let current = null;
  for (const m of messages || []) {
    const c = classifyMessage(m.body);
    const fromHub = !hubPubkey || m.from_pubkey === hubPubkey;
    if (c.variant === 'task' && fromHub) {
      if (current) {
        current.status = 'preempted';
        tasks.push(current);
      }
      current = {
        id: c.task?.slug || `t-${m.seq ?? tasks.length + 1}`,
        seq: m.seq,
        slug: c.task?.slug || null,
        title: c.task?.title || '',
        status: 'working',
        msgs: 1,
      };
    } else if (current) {
      current.msgs += 1;
      if (c.variant === 'done' && fromHub) {
        current.result = c.text || '';
        current.status = closeStatus(current.result);
        tasks.push(current);
        current = null;
      }
    }
  }
  if (current) tasks.push(current);
  return tasks;
}

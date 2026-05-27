const NO_ANSWER_TAGS = [
  ['User cancelled clarification.', 'CANCELLED'],
  ['No response received', 'EXPIRED'],
  ['This run has no live user', 'NO ANSWER'],
  ['No user-facing surface accepted', 'NO ANSWER'],
  ['Clarification handler failed', 'FAILED'],
];

export function askUserNoAnswerTag(result) {
  if (!result) return null;
  for (const [prefix, tag] of NO_ANSWER_TAGS) {
    if (result.startsWith(prefix)) return tag;
  }
  return null;
}

export function isAskUserNoAnswer(result) {
  return askUserNoAnswerTag(result) !== null;
}

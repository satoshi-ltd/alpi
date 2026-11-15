const NO_ANSWER_TAGS = [
  ['User cancelled clarification.', 'Cancelled'],
  ['No response received', 'Expired'],
  ['This run has no live user', 'No answer'],
  ['No user-facing surface accepted', 'No answer'],
  ['Clarification handler failed', 'Failed'],
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

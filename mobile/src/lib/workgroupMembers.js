// host.workgroups.list's `members` is a headcount, not a roster — only host.workgroup.members returns the array.
export function resolveMembers(memberListData) {
  return Array.isArray(memberListData?.members) ? memberListData.members : [];
}

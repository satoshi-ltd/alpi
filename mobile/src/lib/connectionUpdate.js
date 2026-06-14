export function canUpdateConnection(role, updateAvailable) {
  return role === 'admin' && Boolean(updateAvailable);
}

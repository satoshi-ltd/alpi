export function canUpdateConnection(role, updateAvailable, selfUpdate) {
  return role === 'admin' && Boolean(updateAvailable) && selfUpdate !== false;
}

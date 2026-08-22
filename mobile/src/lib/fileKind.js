import { fileKind } from '../../../common/fileKind.mjs';

export { fileKind, fileTypeLabel, fmtSize } from '../../../common/fileKind.mjs';

export function shouldFetchPreview(a, { message, profile }) {
  return !!(message && fileKind(a?.name, a?.mime) === 'image' && !a?.localUri && a?.path && profile);
}

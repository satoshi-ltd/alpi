import { exportFileName, exportHtml, exportMarkdown } from '../../../common/messageExport.mjs';

const A4 = { width: 595, height: 842 };
const KEEP_MS = 10 * 60 * 1000;
const sent = new Map();
let counter = 0;

async function forgetOld(FileSystem) {
  const stale = [...sent].filter(([, at]) => Date.now() - at > KEEP_MS).map(([dir]) => dir);
  for (const dir of stale) sent.delete(dir);
  await Promise.all(stale.map((dir) => FileSystem.deleteAsync(dir, { idempotent: true }).catch(() => {})));
}

async function exportDir(FileSystem) {
  await forgetOld(FileSystem);
  counter += 1;
  const dir = `${FileSystem.cacheDirectory || ''}alpi-export-${Date.now().toString(36)}-${counter}/`;
  await FileSystem.makeDirectoryAsync(dir, { intermediates: true });
  sent.set(dir, Date.now());
  return dir;
}

async function shareFile(uri, mimeType, UTI, name) {
  const Sharing = await import('expo-sharing');
  if (!(await Sharing.isAvailableAsync())) throw new Error('sharing is not available on this device');
  await Sharing.shareAsync(uri, { mimeType, UTI, dialogTitle: name });
}

export async function shareMarkdown(message) {
  const FileSystem = await import('expo-file-system/legacy');
  const name = exportFileName(message, 'md');
  const uri = `${await exportDir(FileSystem)}${name}`;
  await FileSystem.writeAsStringAsync(uri, exportMarkdown(message));
  await shareFile(uri, 'text/markdown', 'net.daringfireball.markdown', name);
}

export async function sharePdf(message, accent) {
  const [FileSystem, Print] = await Promise.all([import('expo-file-system/legacy'), import('expo-print')]);
  const name = exportFileName(message, 'pdf');
  const { uri } = await Print.printToFileAsync({ html: exportHtml(message, { accent }), ...A4 });
  const named = `${await exportDir(FileSystem)}${name}`;
  await FileSystem.moveAsync({ from: uri, to: named });
  await shareFile(named, 'application/pdf', 'com.adobe.pdf', name);
}

export function wgPostSeconds(at) {
  const ms = at ? Date.parse(at) : NaN;
  return Number.isFinite(ms) ? ms / 1000 : 0;
}

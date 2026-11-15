import { ICONS } from '../../common/iconPaths.mjs';

export const COPIED = 'Copied';
export const COPY_FAILED = 'Copy failed, select the text';
export const COPY_HOLD_MS = 1600;

const escape = (text) => String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function icon(name, cls) {
  const body = ICONS[name].map(([tag, attrs]) => `<${tag} ${Object.entries(attrs).map(([k, v]) => `${k}="${v}"`).join(' ')}/>`).join('');
  return `<svg class="copy-glyph ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}

export function copyButton({ text = '', shown, label, className = '', lead = '' }) {
  const cls = ['copy', className].filter(Boolean).join(' ');
  return `<button class="${cls}" type="button" data-copy="${escape(text)}" aria-label="${escape(label)}">${lead}`
    + `<span class="copy-swap copy-icon" aria-hidden="true">${icon('copy', 'copy-idle')}${icon('check', 'copy-done')}</span>`
    + `<span class="copy-swap copy-text" aria-hidden="true"><span class="copy-idle">${shown}</span><span class="copy-done">${COPIED}</span></span></button>`;
}

export function copyCss() {
  return [
    '.copy-swap{display:inline-grid;justify-items:center;align-items:center}',
    '.copy-swap>*{grid-area:1/1}',
    '.copy .copy-done,.copy.is-copied .copy-idle{visibility:hidden}',
    '.copy.is-copied .copy-done{visibility:visible}',
    '.copy-glyph{width:16px;height:16px;display:block}',
    '.sr-only{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}',
  ].join('\n');
}

function wireCopy(copied, failed, hold) {
  const status = document.createElement('div');
  status.className = 'sr-only';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  const mount = () => document.body.appendChild(status);
  if (document.body) mount();
  else document.addEventListener('DOMContentLoaded', mount);
  const announce = (said) => { status.textContent = status.textContent === said ? `${said}\u200b` : said; };
  document.addEventListener('click', (e) => {
    const button = e.target.closest && e.target.closest('button.copy[data-copy]');
    if (!button) return;
    const done = () => {
      button.classList.add('is-copied');
      announce(copied);
      clearTimeout(button.copyTimer);
      button.copyTimer = setTimeout(() => { button.classList.remove('is-copied'); announce(''); }, hold);
    };
    if (!navigator.clipboard) { announce(failed); return; }
    navigator.clipboard.writeText(button.dataset.copy).then(done, () => announce(failed));
  });
}

export function copyScript() {
  return `(${wireCopy.toString()})(${JSON.stringify(COPIED)}, ${JSON.stringify(COPY_FAILED)}, ${COPY_HOLD_MS});`;
}

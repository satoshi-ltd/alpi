export const EMAIL_TYPE_LABELS = {
  imap: 'IMAP',
  gmail: 'Gmail',
};

export const IMAP_FIELDS = [
  { key: 'address', label: 'Email address', secret: false, required: true, hint: 'you@domain.com' },
  { key: 'password', label: 'Password', secret: true, required: true, hint: 'app password if 2FA' },
  { key: 'imap_host', label: 'IMAP host', secret: false, required: true, hint: 'imap.fastmail.com · imap.gmail.com · …' },
  { key: 'imap_port', label: 'IMAP port', secret: false, hint: '993 (SSL) · 143 (STARTTLS)' },
  { key: 'smtp_host', label: 'SMTP host', secret: false, required: true, hint: 'smtp.fastmail.com · smtp.gmail.com · …' },
  { key: 'smtp_port', label: 'SMTP port', secret: false, hint: '587 (STARTTLS) · 465 (SSL)' },
];

// Mirrors the backend's account-id rule (alpi/mail/accounts.py:slug) — underscores, not hyphens.
export function emailSlug(address) {
  return String(address || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

export function isValidEmail(address) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(address || '').trim());
}

// Blank → server default; otherwise must be an integer 1..65535. Never coerce junk to NaN.
export function portValid(value) {
  const t = String(value ?? '').trim();
  if (!t) return true;
  return /^\d+$/.test(t) && Number(t) >= 1 && Number(t) <= 65535;
}

export function buildAddPayload(profile, draft) {
  const payload = {
    profile,
    address: (draft.address || '').trim(),
    password: draft.password || '',
    imap_host: (draft.imap_host || '').trim(),
    smtp_host: (draft.smtp_host || '').trim(),
  };
  const imapPort = (draft.imap_port || '').trim();
  const smtpPort = (draft.smtp_port || '').trim();
  if (imapPort && portValid(imapPort)) payload.imap_port = Number(imapPort);
  if (smtpPort && portValid(smtpPort)) payload.smtp_port = Number(smtpPort);
  return payload;
}

export function isAddReady(draft) {
  return (
    isValidEmail(draft.address) &&
    (draft.password || '').length > 0 &&
    (draft.imap_host || '').trim().length > 0 &&
    (draft.smtp_host || '').trim().length > 0 &&
    portValid(draft.imap_port) &&
    portValid(draft.smtp_port)
  );
}

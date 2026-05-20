// Gateway env keys mirror alpi/host/device_state.py::GATEWAY_ENV_KEYS — fixed schema per gateway.

export const GATEWAY_LABELS = {
  telegram: 'Telegram',
  imap: 'IMAP',
  gmail: 'Gmail',
  matrix: 'Matrix',
};

export const GATEWAY_DESC = {
  telegram: 'Telegram bot',
  imap: 'Email via IMAP',
  gmail: 'Email via Gmail OAuth',
  matrix: 'Matrix bot (no-E2EE MVP)',
};

export const GATEWAY_FIELDS = {
  telegram: [
    { env: 'TELEGRAM_BOT_TOKEN', label: 'Bot token', secret: true, required: true, hint: 'from @BotFather' },
    { env: 'TELEGRAM_ALLOWED_CHAT_IDS', label: 'Allowed chat IDs', secret: false, required: true, hint: 'comma-separated · empty = no inbound (fail-closed)' },
  ],
  imap: [
    { env: 'IMAP_ADDRESS', label: 'Email address', secret: false, required: true, hint: 'you@domain.com' },
    { env: 'IMAP_PASSWORD', label: 'Password', secret: true, required: true, hint: 'app password if 2FA' },
    { env: 'IMAP_HOST', label: 'IMAP host', secret: false, required: true, hint: 'imap.gmail.com · imap.fastmail.com · …' },
    { env: 'IMAP_PORT', label: 'IMAP port', secret: false, required: true, hint: '993 (SSL) · 143 (STARTTLS)' },
    { env: 'SMTP_HOST', label: 'SMTP host', secret: false, required: true, hint: 'smtp.gmail.com · smtp.fastmail.com · …' },
    { env: 'SMTP_PORT', label: 'SMTP port', secret: false, hint: '587 (STARTTLS) · 465 (SSL)' },
    { env: 'IMAP_ALLOWED_SENDERS', label: 'Allowed senders', secret: false, hint: 'comma-separated emails · empty = anyone' },
  ],
  gmail: [
    { env: 'GMAIL_CLIENT_ID', label: 'OAuth client id', secret: false, required: true, hint: 'from Google Cloud Console' },
    { env: 'GMAIL_CLIENT_SECRET', label: 'OAuth client secret', secret: true, required: true },
    { env: 'GMAIL_ALLOWED_SENDERS', label: 'Allowed senders', secret: false, hint: 'comma-separated emails · empty = anyone' },
  ],
  matrix: [
    { env: 'MATRIX_HOMESERVER_URL', label: 'Homeserver URL', secret: false, required: true, hint: 'http://umbrel.local:8008 · https://matrix.example.com' },
    { env: 'MATRIX_USER_ID', label: 'Bot user id', secret: false, required: true, hint: '@alpi-bot:server' },
    { env: 'MATRIX_ACCESS_TOKEN', label: 'Access token', secret: true, required: true, hint: 'from /_matrix/client/r0/login' },
    { env: 'MATRIX_DEVICE_ID', label: 'Device id', secret: false, hint: 'from the login response · optional' },
    { env: 'MATRIX_ALLOWED_ROOMS', label: 'Allowed rooms', secret: false, required: true, hint: 'comma-separated room IDs (!abc:server) · fail-closed' },
    { env: 'MATRIX_ALLOWED_SENDERS', label: 'Allowed senders', secret: false, hint: 'comma-separated user IDs (@user:server) · empty = all room members' },
  ],
};

export const GATEWAY_ORDER = ['telegram', 'imap', 'gmail', 'matrix'];

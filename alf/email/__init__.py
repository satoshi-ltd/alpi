"""Email subsystem — shared IMAP/SMTP client.

Used both by the ``email`` tool (active inbox management — search,
read, send, reply, etc.) and, later, by a gateway email platform that
listens for inbound mail. Credentials and hosts live in ``~/.alf/.env``
under the ``EMAIL_*`` prefix — same pattern as ``TELEGRAM_*``.
"""

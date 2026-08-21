"""Outgoing email over plain authenticated SMTP.

Same delivery contract as the push channels: best-effort, queued on a worker
thread, never propagates into the request. Any mailbox with SMTP access works
(Strato, IONOS, Gmail app passwords, …) — at beta volume there is no need for
a transactional-email provider, and swapping one in later is a config change.
"""

import atexit
import logging
import smtplib
import ssl
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email")
atexit.register(lambda: _executor.shutdown(wait=False))


def send(to: str, subject: str, body: str) -> None:
    """Queues one plain-text email. Returns immediately."""
    settings = get_settings()
    if not settings.email_enabled:
        logger.info("email disabled — would have sent to %s: %s", to, subject)
        return
    _executor.submit(_deliver, to, subject, body)


def _deliver(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=15
            ) as server:
                _login_and_send(server, message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                server.starttls(context=ssl.create_default_context())
                _login_and_send(server, message)
    except Exception:  # noqa: BLE001 — never propagate off the worker
        logger.exception("failed to send email to %s", to)


def _login_and_send(server: smtplib.SMTP, message: EmailMessage) -> None:
    settings = get_settings()
    if settings.smtp_username:
        server.login(settings.smtp_username, settings.smtp_password)
    server.send_message(message)

"""Delivery of push notifications through the Expo push service.

Expo is the transport because the client is an Expo app: `ExponentPushToken[…]`
values come straight from `expo-notifications` and Expo fans them out to APNs
and FCM, so no certificates live in this backend. (The Azure Notification Hub in
`infra/` is the alternative path — see todos.md before choosing it.)

Delivery is best-effort and off the request path: a push that fails must never
turn a successfully-played answer into an HTTP error.
"""

import atexit
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Expo accepts at most 100 messages per request.
MAX_MESSAGES_PER_REQUEST = 100

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="push")
atexit.register(lambda: _executor.shutdown(wait=False))


@dataclass
class PushMessage:
    to: str
    title: str
    body: str
    data: dict = field(default_factory=dict)

    def to_expo_payload(self) -> dict:
        return {
            "to": self.to,
            "title": self.title,
            "body": self.body,
            "data": self.data,
            "sound": "default",
            "channelId": "default",
        }


def is_expo_token(token: str | None) -> bool:
    return bool(token) and token.startswith(("ExponentPushToken[", "ExpoPushToken["))


def send(messages: list[PushMessage]) -> None:
    """Queues messages for delivery. Returns immediately."""
    settings = get_settings()
    messages = [message for message in messages if is_expo_token(message.to)]
    if not messages:
        return

    if not settings.push_enabled:
        logger.info(
            "push disabled — would have sent %d message(s): %s",
            len(messages),
            [message.title for message in messages],
        )
        return

    _executor.submit(_deliver, messages)


def _deliver(messages: list[PushMessage]) -> None:
    settings = get_settings()
    headers = {"accept": "application/json", "content-type": "application/json"}
    if settings.expo_access_token:
        headers["authorization"] = f"Bearer {settings.expo_access_token}"

    for start in range(0, len(messages), MAX_MESSAGES_PER_REQUEST):
        chunk = messages[start : start + MAX_MESSAGES_PER_REQUEST]
        try:
            response = httpx.post(
                settings.expo_push_url,
                json=[message.to_expo_payload() for message in chunk],
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            _log_ticket_errors(response.json())
        except Exception:  # noqa: BLE001 — never propagate into the request
            logger.exception("failed to deliver %d push message(s)", len(chunk))


def _log_ticket_errors(payload: object) -> None:
    """Expo returns HTTP 200 with per-message tickets; errors hide in there.

    `DeviceNotRegistered` means the token is dead and should eventually be
    cleared from the player row — see todos.md for the receipts follow-up.
    """
    if not isinstance(payload, dict):
        return
    for ticket in payload.get("data") or []:
        if isinstance(ticket, dict) and ticket.get("status") == "error":
            logger.warning(
                "expo push ticket error: %s (%s)",
                ticket.get("message"),
                (ticket.get("details") or {}).get("error"),
            )

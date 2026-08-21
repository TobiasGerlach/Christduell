"""Web Push delivery (browsers and installed PWAs) via pywebpush.

The sibling of `push.py` (Expo/native): same contract — best-effort, queued on
a worker thread, never propagates into the request. Enabled by configuring the
VAPID key pair; without keys every send is a logged no-op.

Endpoints returning 404/410 are gone (unsubscribed or expired) and their rows
are deleted from the worker thread with a fresh session.
"""

import atexit
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from pywebpush import WebPushException, webpush
from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.session import engine
from app.models.domain import WebPushSubscription

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="webpush")
atexit.register(lambda: _executor.shutdown(wait=False))


def send_to_player(player_id: int, title: str, body: str, data: dict | None = None) -> None:
    """Queues a notification to every browser this player enabled. Returns immediately."""
    settings = get_settings()
    if not settings.web_push_enabled:
        logger.info("web push disabled — would have sent to player %d: %s", player_id, title)
        return
    _executor.submit(_deliver, player_id, title, body, data or {})


def _deliver(player_id: int, title: str, body: str, data: dict) -> None:
    settings = get_settings()
    payload = json.dumps({"title": title, "body": body, "data": data})
    try:
        with Session(engine) as session:
            subscriptions = list(
                session.exec(
                    select(WebPushSubscription).where(
                        WebPushSubscription.player_id == player_id
                    )
                )
            )
            for subscription in subscriptions:
                try:
                    webpush(
                        subscription_info={
                            "endpoint": subscription.endpoint,
                            "keys": {
                                "p256dh": subscription.p256dh,
                                "auth": subscription.auth,
                            },
                        },
                        data=payload,
                        vapid_private_key=settings.vapid_private_key,
                        vapid_claims={"sub": settings.vapid_subject},
                        timeout=10,
                    )
                except WebPushException as exc:
                    status = exc.response.status_code if exc.response is not None else None
                    if status in (404, 410):
                        # The browser unsubscribed or the endpoint expired.
                        session.delete(subscription)
                        session.commit()
                    else:
                        logger.warning("web push to player %d failed: %s", player_id, exc)
    except Exception:  # noqa: BLE001 — never propagate off the worker
        logger.exception("web push delivery for player %d failed", player_id)

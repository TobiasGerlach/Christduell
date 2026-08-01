"""Subscription entitlement rules.

The tier stored on the player is the *entitlement*; `subscription_valid_until`
is the paid-through date. A player is only treated as paying while both agree,
so a missed webhook or a stalled downgrade job can never hand out free access
indefinitely.
"""

from datetime import datetime

from sqlmodel import Session, select

from app.core.time import utcnow
from app.models.domain import Player, SubscriptionTier


def is_subscription_active(player: Player, now: datetime | None = None) -> bool:
    if player.subscription_tier != SubscriptionTier.PAID:
        return False
    if player.subscription_valid_until is None:
        return False
    return player.subscription_valid_until > (now or utcnow())


def activate_paid(
    session: Session,
    player: Player,
    valid_until: datetime,
    *,
    customer_id: str | None = None,
    subscription_id: str | None = None,
) -> Player:
    player.subscription_tier = SubscriptionTier.PAID
    player.subscription_valid_until = valid_until
    player.subscription_cancel_at_period_end = False
    if customer_id is not None:
        player.billing_customer_id = customer_id
    if subscription_id is not None:
        player.billing_subscription_id = subscription_id
    session.add(player)
    session.commit()
    session.refresh(player)
    return player


def mark_cancelled(session: Session, player: Player) -> Player:
    """Cancel at period end — paid access continues until subscription_valid_until."""
    player.subscription_cancel_at_period_end = True
    session.add(player)
    session.commit()
    session.refresh(player)
    return player


def downgrade_to_research(session: Session, player: Player) -> Player:
    player.subscription_tier = SubscriptionTier.RESEARCH
    player.subscription_valid_until = None
    player.subscription_cancel_at_period_end = False
    player.billing_subscription_id = None
    session.add(player)
    session.commit()
    session.refresh(player)
    return player


def downgrade_expired_subscriptions(session: Session, now: datetime | None = None) -> int:
    """Puts every lapsed paid player back on the research tier. Returns the count.

    Run on a schedule (see `scripts/run-maintenance.sh`); it is also called
    opportunistically whenever a player's own subscription status is read, so a
    missed cron run only delays the downgrade for inactive accounts.
    """
    moment = now or utcnow()
    lapsed = list(
        session.exec(
            select(Player).where(
                Player.subscription_tier == SubscriptionTier.PAID,
                Player.deleted_at.is_(None),
                (Player.subscription_valid_until.is_(None))
                | (Player.subscription_valid_until <= moment),
            )
        )
    )
    for player in lapsed:
        downgrade_to_research(session, player)
    return len(lapsed)

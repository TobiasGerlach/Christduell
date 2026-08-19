"""A deployment that cannot do its job must refuse to start rather than fail later.

These checks only apply outside `environment=local`, so they never get in the way
of development.
"""

import pytest

from app.api.routes import legal
from app.core.config import Settings
from app.main import DEFAULT_SECRET_KEY, _check_production_config


@pytest.fixture(autouse=True)
def filled_legal_pages(monkeypatch):
    """The repo ships the legal pages with [[...]] placeholders, which would
    fail every production check here; that concern has its own tests in
    test_legal.py."""
    monkeypatch.setattr(legal, "unfilled_placeholder_pages", lambda: [])


def production(**overrides) -> Settings:
    base = {
        "environment": "production",
        "secret_key": "a-real-secret",
        "cors_origins": ["https://christduell.example"],
    }
    return Settings(**{**base, **overrides})


def test_a_correct_production_config_starts():
    _check_production_config(production())


def test_local_development_is_never_blocked():
    _check_production_config(Settings(environment="local", secret_key=DEFAULT_SECRET_KEY))


def test_the_development_signing_key_is_refused():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _check_production_config(production(secret_key=DEFAULT_SECRET_KEY))


def test_the_fake_billing_provider_is_refused():
    """It would hand every player a free subscription."""
    with pytest.raises(RuntimeError, match="BILLING_PROVIDER=fake"):
        _check_production_config(production(billing_provider="fake"))


@pytest.mark.parametrize(
    "missing",
    ["stripe_secret_key", "stripe_price_id", "stripe_webhook_secret",
     "billing_success_url", "billing_cancel_url"],
)
def test_incomplete_stripe_configuration_is_refused(missing):
    """Otherwise the subscribe button 503s, or webhooks arrive unverifiable."""
    config = {
        "billing_provider": "stripe",
        "stripe_secret_key": "sk_live_x",
        "stripe_price_id": "price_x",
        "stripe_webhook_secret": "whsec_x",
        "billing_success_url": "https://x/ok",
        "billing_cancel_url": "https://x/no",
    }
    config[missing] = ""
    with pytest.raises(RuntimeError, match=missing.upper()):
        _check_production_config(production(**config))


def test_complete_stripe_configuration_starts():
    _check_production_config(
        production(
            billing_provider="stripe",
            stripe_secret_key="sk_live_x",
            stripe_price_id="price_x",
            stripe_webhook_secret="whsec_x",
            billing_success_url="https://x/ok",
            billing_cancel_url="https://x/no",
        )
    )


def test_push_without_any_allowed_origin_is_refused():
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        _check_production_config(production(push_enabled=True, cors_origins=[]))

"""The legal pages ship with the API, and a deploy with unfilled placeholders
must refuse to start — an Impressum reading "[[VORNAME NACHNAME]]" satisfies
nobody."""

import pytest

from app.api.routes import legal
from app.core.config import Settings
from app.main import _check_production_config


def test_impressum_and_datenschutz_are_served(client):
    for path in ("/impressum", "/datenschutz"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")


def test_the_pages_link_each_other_and_the_app(client):
    impressum = client.get("/impressum").text
    datenschutz = client.get("/datenschutz").text
    assert "/datenschutz" in impressum
    assert "/impressum" in datenschutz
    assert 'href="/"' in impressum and 'href="/"' in datenschutz


def test_unfilled_placeholders_block_a_production_start():
    if not legal.unfilled_placeholder_pages():
        pytest.skip("placeholders already filled in — nothing to refuse")
    with pytest.raises(RuntimeError, match="placeholders"):
        _check_production_config(
            Settings(environment="production", secret_key="a-real-secret")
        )


def test_placeholders_never_block_local_development():
    _check_production_config(Settings(environment="local"))

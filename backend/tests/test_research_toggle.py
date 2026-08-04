"""The research programme has a master switch.

It stays off in production until the consent texts are lawyer-approved —
questionnaires collect religious (Art. 9 GDPR) data, and the beta cohort is a
church youth group, so "we'll sort the wording later" is not an option.
"""

from app.models.domain import ResearchConsent
from app.services.research import (
    CONSENT_VERSION,
    GAMES_REQUIRED_BEFORE_QUESTIONNAIRE,
    get_due_questionnaire,
)
from tests.factories import make_player_client
from tests.test_research import make_finished_duels


def _eligible(client, session):
    participant = make_player_client(session, client, "P", "p@example.com")
    session.add(ResearchConsent(player_id=participant.id))
    make_finished_duels(session, participant.id, GAMES_REQUIRED_BEFORE_QUESTIONNAIRE)
    session.commit()
    return participant


def test_no_questionnaire_is_ever_due_while_disabled(client, session, settings_override):
    settings_override(research_enabled=False)
    participant = _eligible(client, session)

    assert get_due_questionnaire(session, participant.id) is None
    body = participant.get("/research/questionnaire/current").json()
    assert body["due_questionnaire"] is None


def test_consent_cannot_be_given_while_disabled(client, session, settings_override):
    settings_override(research_enabled=False)
    participant = make_player_client(session, client, "P", "p@example.com")

    resp = participant.post("/research/consent", json={"general_consent": True})
    assert resp.status_code == 503


def test_status_reports_the_switch_so_the_app_can_explain_it(
    client, session, settings_override
):
    settings_override(research_enabled=False)
    participant = make_player_client(session, client, "P", "p@example.com")

    body = participant.get("/research/consent").json()
    assert body["research_enabled"] is False


def test_withdrawing_still_works_while_disabled(client, session, settings_override):
    """Turning the programme off must never trap anyone in their consent."""
    participant = make_player_client(session, client, "P", "p@example.com")
    participant.post("/research/consent", json={"general_consent": True})

    settings_override(research_enabled=False)
    assert participant.delete("/research/consent").status_code == 204


def test_the_server_stamps_the_consent_version(client, session):
    """Which consent text was live is a fact about the deployment — a client
    claiming to have agreed to some other version must be ignored."""
    participant = make_player_client(session, client, "P", "p@example.com")
    participant.post(
        "/research/consent",
        json={"general_consent": True, "consent_version": "99.0"},
    )

    consent = session.get(ResearchConsent, participant.id)
    assert consent.consent_version == CONSENT_VERSION

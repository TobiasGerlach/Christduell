

from app.models.domain import Category, Player
from app.services import push
from tests.factories import (
    answer_all_questions,
    make_player,
    make_player_client,
    make_questions_for_category,
    play_round,
)

TOKEN = "ExponentPushToken[abcdefghijklmnopqrstuv]"


def give_push_token(session, player_id: int, token: str = TOKEN) -> None:
    player = session.get(Player, player_id)
    player.push_token = token
    session.add(player)
    session.commit()


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


def test_send_skips_non_expo_tokens(settings_override, monkeypatch):
    settings_override(push_enabled=True)
    submitted = []
    monkeypatch.setattr(push._executor, "submit", lambda fn, msgs: submitted.append(msgs))

    push.send(
        [
            push.PushMessage(to="", title="t", body="b"),
            push.PushMessage(to="garbage-token", title="t", body="b"),
        ]
    )
    assert submitted == []


def test_send_queues_valid_messages_when_enabled(settings_override, monkeypatch):
    settings_override(push_enabled=True)
    submitted = []
    monkeypatch.setattr(push._executor, "submit", lambda fn, msgs: submitted.append(msgs))

    push.send([push.PushMessage(to=TOKEN, title="t", body="b")])
    assert len(submitted) == 1 and submitted[0][0].to == TOKEN


def test_send_does_nothing_while_push_is_disabled(settings_override, monkeypatch):
    settings_override(push_enabled=False)
    submitted = []
    monkeypatch.setattr(push._executor, "submit", lambda fn, msgs: submitted.append(msgs))

    push.send([push.PushMessage(to=TOKEN, title="t", body="b")])
    assert submitted == []


def test_deliver_posts_expo_payload(settings_override, monkeypatch):
    settings_override(push_enabled=True, expo_access_token="secret-token")
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"status": "ok"}]}

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(push.httpx, "post", fake_post)
    push._deliver([push.PushMessage(to=TOKEN, title="Titel", body="Text", data={"a": 1})])

    url, kwargs = calls[0]
    assert url.endswith("/push/send")
    assert kwargs["headers"]["authorization"] == "Bearer secret-token"
    assert kwargs["json"] == [
        {
            "to": TOKEN,
            "title": "Titel",
            "body": "Text",
            "data": {"a": 1},
            "sound": "default",
            "channelId": "default",
        }
    ]


def test_deliver_never_raises_on_transport_failure(settings_override, monkeypatch):
    settings_override(push_enabled=True)

    def explode(url, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(push.httpx, "post", explode)
    # A failed push must not be able to break the request that triggered it.
    push._deliver([push.PushMessage(to=TOKEN, title="t", body="b")])


def test_deliver_chunks_large_batches(settings_override, monkeypatch):
    settings_override(push_enabled=True)
    batch_sizes = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {}

    monkeypatch.setattr(
        push.httpx,
        "post",
        lambda url, **kwargs: (batch_sizes.append(len(kwargs["json"])), FakeResponse())[1],
    )
    push._deliver([push.PushMessage(to=TOKEN, title="t", body="b")] * 250)
    assert batch_sizes == [100, 100, 50]


# ---------------------------------------------------------------------------
# Game events
# ---------------------------------------------------------------------------


def test_challenge_notifies_the_opponent(client, session, captured_pushes):
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    bernd = make_player(session, "Bernd", "bernd@example.com")
    give_push_token(session, bernd.id)

    anna.post("/duels", json={"opponent_id": bernd.id})

    assert len(captured_pushes) == 1
    message = captured_pushes[0]
    assert message.to == TOKEN
    assert "Anna" in message.body
    assert message.data["type"] == "duel_challenge"


def test_answering_notifies_the_player_whose_turn_it_is(session, duel, captured_pushes):
    give_push_token(session, duel.opponent.id)
    make_questions_for_category(session, Category.HISTORY, 3)
    round_id = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds", json={"category": "history"}
    ).json()["round_id"]
    captured_pushes.clear()

    answer_all_questions(duel.challenger, duel.duel_id, round_id)

    # Only the final answer hands the turn over, so exactly one nudge is sent.
    turn_messages = [m for m in captured_pushes if m.data["type"] == "duel_turn"]
    assert len(turn_messages) == 1
    assert turn_messages[0].to == TOKEN
    assert "Challenger" in turn_messages[0].body


def test_finished_duel_notifies_both_players_with_their_own_result(
    session, duel, captured_pushes
):
    give_push_token(session, duel.challenger.id, "ExponentPushToken[challenger-token-xx]")
    give_push_token(session, duel.opponent.id, "ExponentPushToken[opponent-token-xxxx]")

    categories = list(Category)[:8]
    picker, responder = duel.challenger, duel.opponent
    for category in categories:
        # The challenger answers everything correctly, the opponent nothing.
        picker_correct = picker is duel.challenger
        play_round(
            session,
            duel.duel_id,
            picker,
            responder,
            category,
            picker_choices=(0, 0, 0) if picker_correct else (1, 1, 1),
            responder_choices=(1, 1, 1) if picker_correct else (0, 0, 0),
        )
        picker, responder = responder, picker

    finished = [m for m in captured_pushes if m.data["type"] == "duel_finished"]
    assert len(finished) == 2
    by_token = {m.to: m.body for m in finished}
    assert "gewonnen" in by_token["ExponentPushToken[challenger-token-xx]"]
    assert "verloren" in by_token["ExponentPushToken[opponent-token-xxxx]"]


def test_no_push_without_a_registered_token(client, session, captured_pushes):
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    bernd = make_player(session, "Bernd", "bernd@example.com")

    anna.post("/duels", json={"opponent_id": bernd.id})

    # A message is still built, but it carries no token and is dropped by send().
    assert all(m.to is None for m in captured_pushes)


def test_register_and_clear_push_token(client, session):
    anna = make_player_client(session, client, "Anna", "anna@example.com")

    assert anna.post("/notifications/register-token", json={"push_token": TOKEN}).status_code == 204
    session.expire_all()
    assert session.get(Player, anna.id).push_token == TOKEN

    assert anna.delete("/notifications/register-token").status_code == 204
    session.expire_all()
    assert session.get(Player, anna.id).push_token is None


def test_registering_a_token_detaches_it_from_the_previous_account(client, session):
    """Two people using one phone must not receive each other's notifications."""
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    bernd = make_player_client(session, client, "Bernd", "bernd@example.com")

    anna.post("/notifications/register-token", json={"push_token": TOKEN})
    bernd.post("/notifications/register-token", json={"push_token": TOKEN})

    session.expire_all()
    assert session.get(Player, anna.id).push_token is None
    assert session.get(Player, bernd.id).push_token == TOKEN

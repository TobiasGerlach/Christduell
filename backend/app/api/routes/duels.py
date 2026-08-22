import json
import random
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, model_validator
from sqlmodel import Session, col, select

from app.api.deps import CurrentPlayer
from app.core.config import get_settings
from app.core.time import utcnow
from app.db.session import SessionDep
from app.models.domain import (
    Category,
    Duel,
    DuelAnswer,
    DuelRound,
    DuelRoundQuestion,
    DuelStatus,
    Player,
    Question,
)
from app.services.duel_state import (
    QUESTIONS_PER_ROUND,
    TOTAL_ROUNDS,
    DuelAction,
    completed_answer_count,
    compute_duel_scores,
    compute_duel_state,
)
from app.services.notifications import (
    notify_challenged,
    notify_duel_finished,
    notify_your_turn,
)
from app.services.question_selection import (
    available_question_count,
    playable_categories,
    select_questions_for_round,
)
from app.services.rating import update_ratings_after_answer

router = APIRouter(prefix="/duels", tags=["duels"])


def question_time_limit() -> float:
    return get_settings().question_time_limit_seconds


CATEGORY_DISPLAY_NAMES: dict[Category, str] = {
    Category.OLD_TESTAMENT: "Altes Testament",
    Category.NEW_TESTAMENT: "Neues Testament",
    Category.BEYOND_THE_HORIZON: "Über den Tellerrand",
    Category.ANCIENT_LANGUAGES: "Alte Sprachen",
    Category.HISTORY: "Geschichte",
    Category.JESUS_TODAY: "Jesus heute",
    Category.CHURCH_YEAR_FESTIVALS: "Kirchenjahr & Feste",
    Category.PARABLES_MIRACLES: "Gleichnisse & Wunder",
    Category.PSALMS_PRAYERS: "Psalmen & Gebete",
    Category.SYMBOLS_CUSTOMS: "Symbole & Bräuche",
    Category.SAINTS_ROLE_MODELS: "Heilige & Vorbilder",
    Category.FACTS_NUMBERS_DATES: "Zahlen, Daten & Fakten",
    Category.FAITH_POP_CULTURE: "Glaube & Popkultur",
}


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------


class DuelCreateRequest(BaseModel):
    """Challenge someone by id (from search) or directly by email address."""

    opponent_id: int | None = None
    opponent_email: EmailStr | None = None

    @model_validator(mode="after")
    def _exactly_one_target(self) -> "DuelCreateRequest":
        if (self.opponent_id is None) == (self.opponent_email is None):
            raise ValueError("Provide exactly one of opponent_id or opponent_email")
        return self


class DuelSummary(BaseModel):
    id: int
    challenger_id: int
    opponent_id: int
    challenger_display_name: str
    opponent_display_name: str
    status: DuelStatus
    challenger_score: int
    opponent_score: int
    created_at: datetime
    finished_at: datetime | None
    # Enough turn state for the list screen to show "whose move is it" without
    # one /state request per duel: what happens next, who acts, and how far
    # into the current round's questions they are.
    action: DuelAction
    acting_player_id: int | None
    position: int | None


class DuelStateResponse(BaseModel):
    duel_id: int
    # Who is who, so clients can label the score ("Du 5 : 3 Anna") instead of
    # showing two anonymous numbers.
    challenger_id: int
    opponent_id: int
    challenger_display_name: str
    opponent_display_name: str
    status: DuelStatus
    action: DuelAction
    acting_player_id: int | None
    waiting_player_id: int | None
    round_sequence: int | None
    round_id: int | None
    position: int | None
    challenger_score: int
    opponent_score: int


class CategoryRecommendation(BaseModel):
    category: Category
    display_name: str


class CategoryPickRequest(BaseModel):
    category: Category


class QuestionToAnswer(BaseModel):
    round_id: int
    position: int
    question_id: int
    category: Category
    prompt: str
    choices: list[str]
    shown_at: datetime
    seconds_remaining: float


class AnswerSubmitRequest(BaseModel):
    selected_choice_index: int | None = None


class AnswerResult(BaseModel):
    is_correct: bool
    is_timeout: bool
    correct_choice_index: int
    reference: str | None
    explanation: str | None
    round_revealed: bool
    duel_finished: bool
    # What the opponent picked on this question — only present when they
    # answered before us (i.e. we are the second responder). None on both
    # fields means "opponent hasn't played this question yet". Safe to return
    # here because our own answer is already locked in.
    opponent_choice_index: int | None = None
    opponent_is_timeout: bool | None = None


class DuelHistoryAnswer(BaseModel):
    player_id: int
    selected_choice_index: int | None
    is_correct: bool | None
    is_timeout: bool


class DuelHistoryQuestion(BaseModel):
    position: int
    prompt: str
    choices: list[str]
    correct_choice_index: int | None
    reference: str | None
    explanation: str | None
    answers: list[DuelHistoryAnswer]


class DuelHistoryRound(BaseModel):
    sequence: int
    category: Category
    category_display_name: str
    picked_by_id: int
    revealed: bool
    questions: list[DuelHistoryQuestion]


class DuelHistoryResponse(BaseModel):
    duel_id: int
    challenger_id: int
    opponent_id: int
    rounds: list[DuelHistoryRound]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_duel(session: Session, duel_id: int) -> Duel:
    duel = session.get(Duel, duel_id)
    if duel is None:
        raise HTTPException(status_code=404, detail="Duel not found")
    return duel


def _require_participant(duel: Duel, player_id: int) -> None:
    if player_id not in (duel.challenger_id, duel.opponent_id):
        raise HTTPException(status_code=403, detail="Player is not part of this duel")


def _require_round(session: Session, duel: Duel, round_id: int) -> DuelRound:
    duel_round = session.get(DuelRound, round_id)
    if duel_round is None or duel_round.duel_id != duel.id:
        raise HTTPException(status_code=404, detail="Round not found")
    return duel_round


def _require_round_question(session: Session, round_id: int, position: int) -> DuelRoundQuestion:
    if position < 1 or position > QUESTIONS_PER_ROUND:
        raise HTTPException(status_code=404, detail="Invalid question position")
    round_question = session.exec(
        select(DuelRoundQuestion).where(
            DuelRoundQuestion.round_id == round_id, DuelRoundQuestion.position == position
        )
    ).first()
    if round_question is None:
        raise HTTPException(status_code=404, detail="Question not found for this round/position")
    return round_question


def _display_name(session: Session, player_id: int) -> str:
    player = session.get(Player, player_id)
    return player.display_name if player is not None else "Unbekannt"


def _to_summary(session: Session, duel: Duel) -> DuelSummary:
    challenger_score, opponent_score = compute_duel_scores(session, duel)
    state = compute_duel_state(session, duel)
    return DuelSummary(
        action=state.action,
        acting_player_id=state.acting_player_id,
        position=state.position,
        id=duel.id,
        challenger_id=duel.challenger_id,
        opponent_id=duel.opponent_id,
        challenger_display_name=_display_name(session, duel.challenger_id),
        opponent_display_name=_display_name(session, duel.opponent_id),
        status=duel.status,
        challenger_score=challenger_score,
        opponent_score=opponent_score,
        created_at=duel.created_at,
        finished_at=duel.finished_at,
    )


def _to_state_response(session: Session, duel: Duel) -> DuelStateResponse:
    state = compute_duel_state(session, duel)
    challenger_score, opponent_score = compute_duel_scores(session, duel)
    return DuelStateResponse(
        duel_id=duel.id,
        challenger_id=duel.challenger_id,
        opponent_id=duel.opponent_id,
        challenger_display_name=_display_name(session, duel.challenger_id),
        opponent_display_name=_display_name(session, duel.opponent_id),
        status=duel.status,
        action=state.action,
        acting_player_id=state.acting_player_id,
        waiting_player_id=state.waiting_player_id,
        round_sequence=state.round_sequence,
        round_id=state.round_id,
        position=state.position,
        challenger_score=challenger_score,
        opponent_score=opponent_score,
    )


def _require_pick_turn(session: Session, duel: Duel, player_id: int):
    state = compute_duel_state(session, duel)
    if state.action != DuelAction.PICK_CATEGORY or state.acting_player_id != player_id:
        raise HTTPException(
            status_code=409, detail="It is not this player's turn to pick a category"
        )
    return state


def _require_answer_turn(
    session: Session, duel: Duel, round_id: int, position: int, player_id: int
):
    state = compute_duel_state(session, duel)
    if (
        state.action != DuelAction.ANSWER_QUESTION
        or state.round_id != round_id
        or state.acting_player_id != player_id
        or state.position != position
    ):
        raise HTTPException(
            status_code=409, detail="It is not this player's turn to answer this question"
        )
    return state


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _resolve_opponent(session: Session, payload: DuelCreateRequest, challenger: Player) -> Player:
    if payload.opponent_id is not None:
        opponent = session.get(Player, payload.opponent_id)
    else:
        opponent = session.exec(
            select(Player).where(Player.email == payload.opponent_email.strip().lower())
        ).first()

    if opponent is None or opponent.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Spieler nicht gefunden")
    if opponent.id == challenger.id:
        raise HTTPException(status_code=400, detail="Du kannst nicht gegen dich selbst spielen")
    return opponent


@router.post("", response_model=DuelSummary, status_code=201)
def create_duel(
    payload: DuelCreateRequest, player: CurrentPlayer, session: SessionDep
) -> DuelSummary:
    """Challenge another player. The caller is always the challenger."""
    opponent = _resolve_opponent(session, payload, player)

    # Parallel *running* duels between the same two people are fine; a stack of
    # unanswered challenges is just spam. One open challenge per pair.
    open_challenge = session.exec(
        select(Duel.id).where(
            Duel.status == DuelStatus.PENDING,
            (
                ((Duel.challenger_id == player.id) & (Duel.opponent_id == opponent.id))
                | ((Duel.challenger_id == opponent.id) & (Duel.opponent_id == player.id))
            ),
        )
    ).first()
    if open_challenge is not None:
        raise HTTPException(
            status_code=409,
            detail="Zwischen euch gibt es bereits eine offene Herausforderung",
        )

    duel = Duel(challenger_id=player.id, opponent_id=opponent.id)
    session.add(duel)
    session.commit()
    session.refresh(duel)

    notify_challenged(opponent, challenger=player, duel=duel)
    return _to_summary(session, duel)


@router.post("/random", response_model=DuelSummary, status_code=201)
def create_random_duel(player: CurrentPlayer, session: SessionDep) -> DuelSummary:
    """Match against a random other player, preferring similar ratings.

    Deliberately simple: with a small player base a real matchmaking queue would
    just leave people waiting. Revisit once there are enough concurrent players
    for a queue to fill.
    """
    busy_opponent_ids = {
        duel.opponent_id if duel.challenger_id == player.id else duel.challenger_id
        for duel in session.exec(
            select(Duel).where(
                ((Duel.challenger_id == player.id) | (Duel.opponent_id == player.id)),
                col(Duel.status).in_([DuelStatus.PENDING, DuelStatus.ACTIVE]),
            )
        )
    }

    candidates = list(
        session.exec(
            select(Player).where(
                Player.id != player.id,
                Player.deleted_at.is_(None),
                col(Player.id).not_in(busy_opponent_ids or {0}),
            )
        )
    )
    if not candidates:
        raise HTTPException(
            status_code=409,
            detail="Gerade ist niemand für ein Zufallsduell verfügbar",
        )

    candidates.sort(key=lambda candidate: abs(candidate.rating - player.rating))
    # Pick from the closest few rather than the single closest, so repeat
    # matchmaking doesn't pair the same two people over and over.
    opponent = random.choice(candidates[:5])

    duel = Duel(challenger_id=player.id, opponent_id=opponent.id)
    session.add(duel)
    session.commit()
    session.refresh(duel)

    notify_challenged(opponent, challenger=player, duel=duel)
    return _to_summary(session, duel)


@router.get("", response_model=list[DuelSummary])
def list_duels_for_player(player: CurrentPlayer, session: SessionDep) -> list[DuelSummary]:
    statement = (
        select(Duel)
        .where(
            ((Duel.challenger_id == player.id) | (Duel.opponent_id == player.id)),
            Duel.status != DuelStatus.DECLINED,
        )
        .order_by(col(Duel.created_at).desc())
    )
    duels = list(session.exec(statement))
    return [_to_summary(session, duel) for duel in duels]


@router.post("/{duel_id}/decline", response_model=DuelSummary)
def decline_duel(duel_id: int, player: CurrentPlayer, session: SessionDep) -> DuelSummary:
    """Reject a challenge you didn't want. Only possible before the first round."""
    duel = _require_duel(session, duel_id)
    _require_participant(duel, player.id)
    if duel.opponent_id != player.id:
        raise HTTPException(status_code=403, detail="Nur der Herausgeforderte kann ablehnen")
    if duel.status != DuelStatus.PENDING:
        raise HTTPException(status_code=409, detail="Dieses Duell läuft bereits")

    duel.status = DuelStatus.DECLINED
    session.add(duel)
    session.commit()
    session.refresh(duel)
    return _to_summary(session, duel)


@router.get("/{duel_id}/state", response_model=DuelStateResponse)
def get_duel_state(duel_id: int, player: CurrentPlayer, session: SessionDep) -> DuelStateResponse:
    duel = _require_duel(session, duel_id)
    _require_participant(duel, player.id)
    return _to_state_response(session, duel)


@router.get("/{duel_id}/recommendations", response_model=list[CategoryRecommendation])
def get_category_recommendations(
    duel_id: int, player: CurrentPlayer, session: SessionDep
) -> list[CategoryRecommendation]:
    duel = _require_duel(session, duel_id)
    _require_participant(duel, player.id)
    _require_pick_turn(session, duel, player.id)

    used = set(session.exec(select(DuelRound.category).where(DuelRound.duel_id == duel_id)))
    # Only offer categories that still hold enough questions — a retired-out
    # category would 409 the moment the player tapped it.
    unused = playable_categories(session, QUESTIONS_PER_ROUND, exclude=used)
    if not unused:
        raise HTTPException(
            status_code=409,
            detail="Zurzeit sind nicht genug Fragen für eine weitere Runde verfügbar",
        )
    sample = random.sample(unused, min(3, len(unused)))
    return [
        CategoryRecommendation(category=category, display_name=CATEGORY_DISPLAY_NAMES[category])
        for category in sample
    ]


@router.post("/{duel_id}/rounds", response_model=DuelStateResponse, status_code=201)
def pick_category(
    duel_id: int, payload: CategoryPickRequest, player: CurrentPlayer, session: SessionDep
) -> DuelStateResponse:
    duel = _require_duel(session, duel_id)
    _require_participant(duel, player.id)
    if duel.status == DuelStatus.DECLINED:
        raise HTTPException(status_code=409, detail="Dieses Duell wurde abgelehnt")
    state = _require_pick_turn(session, duel, player.id)

    already_used = session.exec(
        select(DuelRound.id).where(
            DuelRound.duel_id == duel_id, DuelRound.category == payload.category
        )
    ).first()
    if already_used is not None:
        raise HTTPException(status_code=409, detail="Category already used in this duel")

    # Checked before the round is created: reported questions can retire a
    # category below a full round, and a half-created round would wedge the duel.
    if available_question_count(session, payload.category) < QUESTIONS_PER_ROUND:
        raise HTTPException(
            status_code=409,
            detail="In dieser Kategorie sind zurzeit nicht genug Fragen verfügbar",
        )

    responder_id = state.waiting_player_id

    duel_round = DuelRound(
        duel_id=duel_id,
        sequence=state.round_sequence,
        category=payload.category,
        picked_by_id=player.id,
        first_responder_id=player.id,
        second_responder_id=responder_id,
    )
    session.add(duel_round)
    session.flush()

    questions = select_questions_for_round(
        session, payload.category, player.rating, count=QUESTIONS_PER_ROUND
    )
    if len(questions) < QUESTIONS_PER_ROUND:
        # Only reachable if a question retired between the check above and here.
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="In dieser Kategorie sind zurzeit nicht genug Fragen verfügbar",
        )

    for position, question in enumerate(questions, start=1):
        session.add(
            DuelRoundQuestion(
                round_id=duel_round.id, question_id=question.id, position=position
            )
        )

    if duel.status == DuelStatus.PENDING:
        duel.status = DuelStatus.ACTIVE
        session.add(duel)

    session.commit()
    session.refresh(duel)
    return _to_state_response(session, duel)


@router.get(
    "/{duel_id}/rounds/{round_id}/questions/{position}",
    response_model=QuestionToAnswer,
)
def get_round_question(
    duel_id: int, round_id: int, position: int, player: CurrentPlayer, session: SessionDep
) -> QuestionToAnswer:
    duel = _require_duel(session, duel_id)
    _require_participant(duel, player.id)
    duel_round = _require_round(session, duel, round_id)
    round_question = _require_round_question(session, round_id, position)
    _require_answer_turn(session, duel, round_id, position, player.id)

    question = session.get(Question, round_question.question_id)

    answer = session.exec(
        select(DuelAnswer).where(
            DuelAnswer.round_id == round_id,
            DuelAnswer.question_id == question.id,
            DuelAnswer.player_id == player.id,
        )
    ).first()
    if answer is None:
        answer = DuelAnswer(round_id=round_id, question_id=question.id, player_id=player.id)
        session.add(answer)
        session.commit()
        session.refresh(answer)

    elapsed_seconds = (utcnow() - answer.shown_at).total_seconds()
    seconds_remaining = max(0.0, question_time_limit() - elapsed_seconds)

    return QuestionToAnswer(
        round_id=round_id,
        position=position,
        question_id=question.id,
        category=duel_round.category,
        prompt=question.prompt,
        choices=json.loads(question.choices),
        # Stored as a naive UTC timestamp; attach tzinfo so the serialized
        # ISO string carries an explicit offset — otherwise JS `Date` parses
        # offset-less date-times as local time, skewing the client countdown
        # by the local UTC offset (it appeared to expire immediately in CEST).
        shown_at=answer.shown_at.replace(tzinfo=UTC),
        seconds_remaining=seconds_remaining,
    )


@router.post(
    "/{duel_id}/rounds/{round_id}/questions/{position}/answer",
    response_model=AnswerResult,
)
def submit_answer(
    duel_id: int,
    round_id: int,
    position: int,
    payload: AnswerSubmitRequest,
    player: CurrentPlayer,
    session: SessionDep,
) -> AnswerResult:
    duel = _require_duel(session, duel_id)
    _require_participant(duel, player.id)
    duel_round = _require_round(session, duel, round_id)
    round_question = _require_round_question(session, round_id, position)
    _require_answer_turn(session, duel, round_id, position, player.id)

    question = session.get(Question, round_question.question_id)

    answer = session.exec(
        select(DuelAnswer).where(
            DuelAnswer.round_id == round_id,
            DuelAnswer.question_id == question.id,
            DuelAnswer.player_id == player.id,
        )
    ).first()
    if answer is None or answer.answered_at is not None:
        raise HTTPException(
            status_code=409, detail="Question has not been shown yet, or was already answered"
        )

    now = utcnow()
    elapsed_ms = int((now - answer.shown_at).total_seconds() * 1000)
    # Server is authoritative on timing — a late submission is forced to a
    # timeout regardless of what the client thinks it sent.
    timed_out = (
        payload.selected_choice_index is None
        or elapsed_ms > question_time_limit() * 1000
    )

    answer.answered_at = now
    answer.selected_choice_index = payload.selected_choice_index
    answer.response_time_ms = elapsed_ms
    answer.is_timeout = timed_out
    answer.is_correct = (not timed_out) and (
        payload.selected_choice_index == question.correct_choice_index
    )
    session.add(answer)

    update_ratings_after_answer(player, question, answer.is_correct)
    session.add(player)
    session.add(question)
    session.flush()

    is_first_responder = player.id == duel_round.first_responder_id
    completed_count = completed_answer_count(session, round_id, player.id)
    round_revealed = False
    duel_finished = False
    if completed_count == QUESTIONS_PER_ROUND:
        if is_first_responder:
            duel_round.first_responder_completed_at = now
        else:
            duel_round.second_responder_completed_at = now
            duel_round.revealed_at = now
            round_revealed = True
            if duel_round.sequence == TOTAL_ROUNDS:
                duel.status = DuelStatus.FINISHED
                duel.finished_at = now
                duel_finished = True
                session.add(duel)
        session.add(duel_round)

    # The opponent's pick on the same question, if they already played it.
    # Revealed only now that our own answer is committed.
    opponent_id = (
        duel.opponent_id if player.id == duel.challenger_id else duel.challenger_id
    )
    opponent_answer = session.exec(
        select(DuelAnswer).where(
            DuelAnswer.round_id == round_id,
            DuelAnswer.question_id == question.id,
            DuelAnswer.player_id == opponent_id,
            DuelAnswer.answered_at.is_not(None),
        )
    ).first()

    session.commit()

    if duel_finished:
        notify_duel_finished(session, duel)
    else:
        # Whoever the state machine hands control to next gets the nudge — that
        # is the only moment the app has something new for them to do.
        next_state = compute_duel_state(session, duel)
        if next_state.acting_player_id is not None and next_state.acting_player_id != player.id:
            notify_your_turn(session, duel, next_state.acting_player_id, opponent=player)

    return AnswerResult(
        is_correct=answer.is_correct,
        is_timeout=answer.is_timeout,
        correct_choice_index=question.correct_choice_index,
        reference=question.reference,
        explanation=question.explanation,
        round_revealed=round_revealed,
        duel_finished=duel_finished,
        opponent_choice_index=opponent_answer.selected_choice_index if opponent_answer else None,
        opponent_is_timeout=opponent_answer.is_timeout if opponent_answer else None,
    )


@router.get("/{duel_id}/history", response_model=DuelHistoryResponse)
def get_duel_history(
    duel_id: int, player: CurrentPlayer, session: SessionDep
) -> DuelHistoryResponse:
    duel = _require_duel(session, duel_id)
    _require_participant(duel, player.id)
    player_id = player.id

    rounds = list(
        session.exec(
            select(DuelRound).where(DuelRound.duel_id == duel_id).order_by(DuelRound.sequence)
        )
    )

    history_rounds: list[DuelHistoryRound] = []
    for duel_round in rounds:
        revealed = duel_round.revealed_at is not None
        round_questions = list(
            session.exec(
                select(DuelRoundQuestion)
                .where(DuelRoundQuestion.round_id == duel_round.id)
                .order_by(DuelRoundQuestion.position)
            )
        )

        questions: list[DuelHistoryQuestion] = []
        for round_question in round_questions:
            question = session.get(Question, round_question.question_id)
            answers = list(
                session.exec(
                    select(DuelAnswer).where(
                        DuelAnswer.round_id == duel_round.id,
                        DuelAnswer.question_id == question.id,
                    )
                )
            )
            visible_answers = [
                DuelHistoryAnswer(
                    player_id=answer.player_id,
                    selected_choice_index=answer.selected_choice_index,
                    is_correct=answer.is_correct,
                    is_timeout=answer.is_timeout,
                )
                for answer in answers
                if revealed or answer.player_id == player_id
            ]
            questions.append(
                DuelHistoryQuestion(
                    position=round_question.position,
                    prompt=question.prompt,
                    choices=json.loads(question.choices),
                    correct_choice_index=question.correct_choice_index if revealed else None,
                    # Withheld until the round reveals, like the answer key.
                    reference=question.reference if revealed else None,
                    explanation=question.explanation if revealed else None,
                    answers=visible_answers,
                )
            )

        history_rounds.append(
            DuelHistoryRound(
                sequence=duel_round.sequence,
                category=duel_round.category,
                category_display_name=CATEGORY_DISPLAY_NAMES[duel_round.category],
                picked_by_id=duel_round.picked_by_id,
                revealed=revealed,
                questions=questions,
            )
        )

    return DuelHistoryResponse(
        duel_id=duel.id,
        challenger_id=duel.challenger_id,
        opponent_id=duel.opponent_id,
        rounds=history_rounds,
    )

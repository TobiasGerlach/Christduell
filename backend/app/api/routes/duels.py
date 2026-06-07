import json
import random
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

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
from app.services.notifications import notify_opponent_answered
from app.services.question_selection import select_questions_for_round
from app.services.rating import update_ratings_after_answer

router = APIRouter(prefix="/duels", tags=["duels"])

QUESTION_TIME_LIMIT_SECONDS = 30.0

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
    challenger_id: int
    opponent_id: int


class DuelSummary(BaseModel):
    id: int
    challenger_id: int
    opponent_id: int
    status: DuelStatus
    challenger_score: int
    opponent_score: int
    created_at: datetime
    finished_at: datetime | None


class DuelStateResponse(BaseModel):
    duel_id: int
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
    player_id: int
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
    player_id: int
    selected_choice_index: int | None = None


class AnswerResult(BaseModel):
    is_correct: bool
    is_timeout: bool
    correct_choice_index: int
    round_revealed: bool
    duel_finished: bool


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


def _to_summary(session: Session, duel: Duel) -> DuelSummary:
    challenger_score, opponent_score = compute_duel_scores(session, duel)
    return DuelSummary(
        id=duel.id,
        challenger_id=duel.challenger_id,
        opponent_id=duel.opponent_id,
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
        raise HTTPException(status_code=409, detail="It is not this player's turn to pick a category")
    return state


def _require_answer_turn(session: Session, duel: Duel, round_id: int, position: int, player_id: int):
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


@router.post("", response_model=DuelSummary, status_code=201)
def create_duel(payload: DuelCreateRequest, session: SessionDep) -> DuelSummary:
    if payload.challenger_id == payload.opponent_id:
        raise HTTPException(status_code=400, detail="Challenger and opponent must differ")

    for player_id in (payload.challenger_id, payload.opponent_id):
        if session.get(Player, player_id) is None:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    duel = Duel(challenger_id=payload.challenger_id, opponent_id=payload.opponent_id)
    session.add(duel)
    session.commit()
    session.refresh(duel)
    return _to_summary(session, duel)


@router.get("", response_model=list[DuelSummary])
def list_duels_for_player(player_id: int, session: SessionDep) -> list[DuelSummary]:
    statement = (
        select(Duel)
        .where((Duel.challenger_id == player_id) | (Duel.opponent_id == player_id))
        .order_by(Duel.created_at.desc())
    )
    duels = list(session.exec(statement))
    return [_to_summary(session, duel) for duel in duels]


@router.get("/{duel_id}/state", response_model=DuelStateResponse)
def get_duel_state(duel_id: int, player_id: int, session: SessionDep) -> DuelStateResponse:
    duel = _require_duel(session, duel_id)
    _require_participant(duel, player_id)
    return _to_state_response(session, duel)


@router.get("/{duel_id}/recommendations", response_model=list[CategoryRecommendation])
def get_category_recommendations(
    duel_id: int, player_id: int, session: SessionDep
) -> list[CategoryRecommendation]:
    duel = _require_duel(session, duel_id)
    _require_participant(duel, player_id)
    _require_pick_turn(session, duel, player_id)

    used = set(session.exec(select(DuelRound.category).where(DuelRound.duel_id == duel_id)))
    unused = [category for category in Category if category not in used]
    sample = random.sample(unused, min(3, len(unused)))
    return [
        CategoryRecommendation(category=category, display_name=CATEGORY_DISPLAY_NAMES[category])
        for category in sample
    ]


@router.post("/{duel_id}/rounds", response_model=DuelStateResponse, status_code=201)
def pick_category(duel_id: int, payload: CategoryPickRequest, session: SessionDep) -> DuelStateResponse:
    duel = _require_duel(session, duel_id)
    _require_participant(duel, payload.player_id)
    state = _require_pick_turn(session, duel, payload.player_id)

    already_used = session.exec(
        select(DuelRound.id).where(
            DuelRound.duel_id == duel_id, DuelRound.category == payload.category
        )
    ).first()
    if already_used is not None:
        raise HTTPException(status_code=409, detail="Category already used in this duel")

    picker = session.get(Player, payload.player_id)
    responder_id = state.waiting_player_id

    duel_round = DuelRound(
        duel_id=duel_id,
        sequence=state.round_sequence,
        category=payload.category,
        picked_by_id=payload.player_id,
        first_responder_id=payload.player_id,
        second_responder_id=responder_id,
    )
    session.add(duel_round)
    session.flush()

    questions = select_questions_for_round(
        session, payload.category, picker.rating, count=QUESTIONS_PER_ROUND
    )
    if len(questions) < QUESTIONS_PER_ROUND:
        raise HTTPException(
            status_code=500, detail="Not enough questions available for this category"
        )

    for position, question in enumerate(questions, start=1):
        session.add(DuelRoundQuestion(round_id=duel_round.id, question_id=question.id, position=position))

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
    duel_id: int, round_id: int, position: int, player_id: int, session: SessionDep
) -> QuestionToAnswer:
    duel = _require_duel(session, duel_id)
    _require_participant(duel, player_id)
    duel_round = _require_round(session, duel, round_id)
    round_question = _require_round_question(session, round_id, position)
    _require_answer_turn(session, duel, round_id, position, player_id)

    question = session.get(Question, round_question.question_id)

    answer = session.exec(
        select(DuelAnswer).where(
            DuelAnswer.round_id == round_id,
            DuelAnswer.question_id == question.id,
            DuelAnswer.player_id == player_id,
        )
    ).first()
    if answer is None:
        answer = DuelAnswer(round_id=round_id, question_id=question.id, player_id=player_id)
        session.add(answer)
        session.commit()
        session.refresh(answer)

    elapsed_seconds = (datetime.utcnow() - answer.shown_at).total_seconds()
    seconds_remaining = max(0.0, QUESTION_TIME_LIMIT_SECONDS - elapsed_seconds)

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
        shown_at=answer.shown_at.replace(tzinfo=timezone.utc),
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
    session: SessionDep,
) -> AnswerResult:
    duel = _require_duel(session, duel_id)
    _require_participant(duel, payload.player_id)
    duel_round = _require_round(session, duel, round_id)
    round_question = _require_round_question(session, round_id, position)
    _require_answer_turn(session, duel, round_id, position, payload.player_id)

    question = session.get(Question, round_question.question_id)

    answer = session.exec(
        select(DuelAnswer).where(
            DuelAnswer.round_id == round_id,
            DuelAnswer.question_id == question.id,
            DuelAnswer.player_id == payload.player_id,
        )
    ).first()
    if answer is None or answer.answered_at is not None:
        raise HTTPException(
            status_code=409, detail="Question has not been shown yet, or was already answered"
        )

    now = datetime.utcnow()
    elapsed_ms = int((now - answer.shown_at).total_seconds() * 1000)
    # Server is authoritative on timing — a late submission is forced to a
    # timeout regardless of what the client thinks it sent.
    timed_out = payload.selected_choice_index is None or elapsed_ms > QUESTION_TIME_LIMIT_SECONDS * 1000

    answer.answered_at = now
    answer.selected_choice_index = payload.selected_choice_index
    answer.response_time_ms = elapsed_ms
    answer.is_timeout = timed_out
    answer.is_correct = (not timed_out) and (payload.selected_choice_index == question.correct_choice_index)
    session.add(answer)

    player = session.get(Player, payload.player_id)
    update_ratings_after_answer(player, question, answer.is_correct)
    session.add(player)
    session.add(question)
    session.flush()

    is_first_responder = payload.player_id == duel_round.first_responder_id
    completed_count = completed_answer_count(session, round_id, payload.player_id)
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

    session.commit()

    notify_opponent_answered(duel, duel_round, payload.player_id)

    return AnswerResult(
        is_correct=answer.is_correct,
        is_timeout=answer.is_timeout,
        correct_choice_index=question.correct_choice_index,
        round_revealed=round_revealed,
        duel_finished=duel_finished,
    )


@router.get("/{duel_id}/history", response_model=DuelHistoryResponse)
def get_duel_history(duel_id: int, player_id: int, session: SessionDep) -> DuelHistoryResponse:
    duel = _require_duel(session, duel_id)
    _require_participant(duel, player_id)

    rounds = list(
        session.exec(select(DuelRound).where(DuelRound.duel_id == duel_id).order_by(DuelRound.sequence))
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

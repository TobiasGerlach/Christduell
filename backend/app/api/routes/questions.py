from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import CurrentPlayer
from app.db.session import SessionDep
from app.models.domain import Question, ReportReason
from app.services.question_reports import has_answered, report_question

router = APIRouter(prefix="/questions", tags=["questions"])

MAX_NOTE_LENGTH = 500


class QuestionReportRequest(BaseModel):
    reason: ReportReason
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)


class QuestionReportResponse(BaseModel):
    status: str
    # True when this report was the one that pulled the question out of
    # circulation. The client says thank you either way.
    question_retired: bool


@router.post("/{question_id}/report", response_model=QuestionReportResponse, status_code=201)
def report(
    question_id: int,
    payload: QuestionReportRequest,
    player: CurrentPlayer,
    session: SessionDep,
) -> QuestionReportResponse:
    """Reports a problem with a question the player has played.

    Restricted to questions the reporter has actually answered — otherwise the
    endpoint would be a way to retire any question in the bank without ever
    seeing it.
    """
    question = session.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Frage nicht gefunden")

    if not has_answered(session, player.id, question_id):
        raise HTTPException(
            status_code=403,
            detail="Du kannst nur Fragen melden, die du selbst gespielt hast",
        )

    _, retired = report_question(
        session,
        question=question,
        player_id=player.id,
        reason=payload.reason,
        note=payload.note,
    )
    return QuestionReportResponse(status="received", question_retired=retired)

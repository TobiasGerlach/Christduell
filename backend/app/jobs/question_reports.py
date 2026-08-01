"""Triage what players reported. Run with `make reports`.

Questions that enough players dispute retire themselves, so this is not an
emergency queue — it is where you go to decide whether a reported question was
actually wrong.

    make reports                  # everything with open reports, worst first
    make reports a="fix 42"       # mark #42's reports resolved (you fixed it)
    make reports a="keep 42"      # dismiss the reports and put #42 back in play
"""

import argparse
import json
import sys

from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models.domain import Question, QuestionReport, ReportStatus
from app.services.question_reports import resolve, restore


def show(session: Session) -> int:
    reports = list(
        session.exec(select(QuestionReport).where(QuestionReport.status == ReportStatus.OPEN))
    )
    if not reports:
        print("No open question reports.")
        return 0

    grouped: dict[int, list[QuestionReport]] = {}
    for report in reports:
        grouped.setdefault(report.question_id, []).append(report)

    # Most-reported first — that ordering is the whole point of the screen.
    for question_id, group in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        question = session.get(Question, question_id)
        if question is None:
            continue
        choices = json.loads(question.choices)
        state = "RETIRED — not being dealt" if question.retired_at else "still in circulation"
        print(f"\n#{question.id}  {question.category.value}  ({len(group)} report(s), {state})")
        print(f"  {question.prompt}")
        for index, choice in enumerate(choices):
            marker = "✓" if index == question.correct_choice_index else " "
            print(f"    {marker} {choice}")
        if question.reference or question.explanation:
            print(f"    ↳ {question.explanation or ''} {question.reference or ''}".rstrip())
        for report in group:
            note = f" — {report.note}" if report.note else ""
            print(f"    · {report.reason.value}{note}")

    print(f"\n{len(grouped)} question(s) with open reports.")
    print("Fix the text in backend/app/db/fixtures/questions/<category>.json, then:")
    print("  make reports a=\"fix <id>\"    after correcting it")
    print("  make reports a=\"keep <id>\"   if the question was fine after all")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=["list", "fix", "keep"], default="list")
    parser.add_argument("question_id", nargs="?", type=int)
    args = parser.parse_args()

    # The jobs talk to the database without booting the app, so nothing else
    # would have applied a pending migration.
    init_db()

    with Session(engine) as session:
        if args.action == "list":
            return show(session)

        if args.question_id is None:
            print(f"Usage: make reports a=\"{args.action} <question-id>\"", file=sys.stderr)
            return 2

        question = session.get(Question, args.question_id)
        if question is None:
            print(f"No question #{args.question_id}", file=sys.stderr)
            return 1

        if args.action == "fix":
            # The text was corrected in the fixtures; re-seeding applies it.
            closed = resolve(session, question.id, ReportStatus.RESOLVED)
            restore(session, question)
            print(f"#{question.id}: closed {closed} report(s) and put it back in circulation.")
            print("Remember to `make seed` so the corrected text reaches the database.")
        else:
            restore(session, question)
            print(f"#{question.id}: reports dismissed, back in circulation.")
        return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Builds the offline proofreading page from the question fixtures.

The questions are inlined into the HTML rather than fetched, so the result is a
single file that works from disk with no server and no network — open it,
review, export.

    make review        # builds and opens it
"""

import json
import sys
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "backend" / "app" / "db" / "fixtures" / "questions"
TEMPLATE = REPO_ROOT / "scripts" / "review" / "template.html"
OUTPUT = REPO_ROOT / "scripts" / "review" / "review.html"

PLACEHOLDER = "__QUESTIONS__"


def load_questions() -> list[dict]:
    questions: list[dict] = []
    for path in sorted(FIXTURES.glob("*.json")):
        questions.extend(json.loads(path.read_text(encoding="utf-8")))
    return questions


def main() -> int:
    questions = load_questions()
    if not questions:
        print(f"No question fixtures found under {FIXTURES}", file=sys.stderr)
        return 1

    template = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        print(f"{TEMPLATE} is missing the {PLACEHOLDER} placeholder", file=sys.stderr)
        return 1

    # </script> inside the data would close the tag early; nothing in the
    # fixtures contains it today, but a future question about HTML might.
    payload = json.dumps(questions, ensure_ascii=False).replace("</", "<\\/")
    OUTPUT.write_text(template.replace(PLACEHOLDER, payload), encoding="utf-8")

    by_category: dict[str, int] = {}
    for question in questions:
        by_category[question["category"]] = by_category.get(question["category"], 0) + 1

    print(f"Built {OUTPUT.relative_to(REPO_ROOT)} with {len(questions)} questions")
    for category, count in sorted(by_category.items()):
        print(f"  {category:24} {count:3}")
    print("\nProgress is stored in the browser, so you can close it and pick up later.")
    print("When you're done (or partway), hit Export and run:")
    print("  make apply-review f=~/Downloads/question-review.json")

    if "--no-open" not in sys.argv:
        webbrowser.open(OUTPUT.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())

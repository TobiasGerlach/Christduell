#!/usr/bin/env python3
"""Applies a review export back to the question fixtures.

Edits made in the review page are written into the JSON files; questions that
were merely flagged are printed as a to-do list, because "this feels wrong" is
not something a script should act on by itself.

    make apply-review f=~/Downloads/question-review.json
    make apply-review f=... dry=1     # show what would change, write nothing
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "backend" / "app" / "db" / "fixtures" / "questions"

EDITABLE = ("prompt", "choices", "correct_choice_index", "reference", "explanation")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: apply_review.py <question-review.json> [--dry-run]", file=sys.stderr)
        return 2

    export_path = Path(sys.argv[1]).expanduser()
    dry_run = "--dry-run" in sys.argv
    if not export_path.exists():
        print(f"No such file: {export_path}", file=sys.stderr)
        return 1

    export = json.loads(export_path.read_text(encoding="utf-8"))
    reviews = export.get("reviews", [])
    edits = [r for r in reviews if r.get("verdict") == "edit" and r.get("edits")]
    flags = [r for r in reviews if r.get("verdict") == "flag"]
    mismatches = [
        r for r in reviews
        if r.get("reviewer_pick") is not None and r["reviewer_pick"] != r.get("stored_key")
    ]

    # Index the fixtures by (category, prompt) — the prompt in the export is
    # always the original, so an edited prompt still finds its row.
    files: dict[str, list[dict]] = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURES.glob("*.json"))
    }
    lookup = {
        (category, entry["prompt"]): entry
        for category, entries in files.items()
        for entry in entries
    }

    applied, missing = 0, []
    changed_files: set[str] = set()
    for review in edits:
        key = (review["category"], review["prompt"])
        entry = lookup.get(key)
        if entry is None:
            missing.append(key)
            continue

        changes = {
            field: review["edits"][field]
            for field in EDITABLE
            if field in review["edits"] and review["edits"][field] != entry.get(field)
        }
        if not changes:
            continue

        print(f"\n{review['category']}: {entry['prompt'][:70]}")
        for field, value in changes.items():
            print(f"    {field}: {entry.get(field)!r}\n      → {value!r}")
        if not dry_run:
            entry.update(changes)
            changed_files.add(review["category"])
        applied += 1

    if not dry_run:
        for category in changed_files:
            path = FIXTURES / f"{category}.json"
            path.write_text(
                json.dumps(files[category], ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    print(f"\n{'Would apply' if dry_run else 'Applied'} {applied} edit(s) "
          f"across {len(changed_files) or len({r['category'] for r in edits})} file(s)")

    if missing:
        print(f"\n{len(missing)} edit(s) could not be matched — the fixture text changed since "
              f"the review page was built:")
        for category, prompt in missing:
            print(f"  {category}: {prompt[:70]}")

    if mismatches:
        print(f"\n{len(mismatches)} question(s) where your answer differed from the stored key:")
        for review in mismatches:
            marker = "handled" if review["verdict"] in ("edit", "flag") else "STILL OPEN"
            print(f"  [{marker}] {review['category']}: {review['prompt'][:60]}")

    if flags:
        print(f"\n{len(flags)} flagged question(s) to fix by hand:")
        for review in flags:
            note = f" — {review['note']}" if review.get("note") else ""
            print(f"  {review['category']}: {review['prompt'][:60]}{note}")

    if not dry_run and applied:
        print("\nNow run:  make check && make reset-db")
    return 0


if __name__ == "__main__":
    sys.exit(main())

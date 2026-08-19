"""Impressum and Datenschutzerklärung, served by the API itself.

The pages live in app/static/legal/ so the one deployed container carries
everything the law requires alongside the app. Personal details are [[...]]
placeholders in the repo; `_check_production_config` refuses to deploy while
any remain unfilled.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

LEGAL_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "legal"
PLACEHOLDER_MARKER = "[["

router = APIRouter(tags=["legal"])


@router.get("/impressum", include_in_schema=False)
def impressum() -> FileResponse:
    return FileResponse(LEGAL_DIR / "impressum.html", media_type="text/html")


@router.get("/datenschutz", include_in_schema=False)
def datenschutz() -> FileResponse:
    return FileResponse(LEGAL_DIR / "datenschutz.html", media_type="text/html")


def unfilled_placeholder_pages() -> list[str]:
    """Names of legal pages still containing [[...]] placeholders."""
    return [
        page.name
        for page in sorted(LEGAL_DIR.glob("*.html"))
        if PLACEHOLDER_MARKER in page.read_text(encoding="utf-8")
    ]

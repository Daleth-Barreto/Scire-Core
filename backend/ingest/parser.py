from pathlib import Path

from pypdf import PdfReader


def extract_text(path: str | Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()

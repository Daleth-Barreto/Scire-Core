from pathlib import Path

from pypdf import PdfReader


def extract_text(path: str | Path) -> str:
    path = Path(path)
    if path.suffix.lower() in (".txt", ".md"):
        return path.read_text(encoding="utf-8").strip()
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()

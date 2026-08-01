import re
from pathlib import Path

_LINE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def set_env_value(path: str | Path, key: str, value: str) -> None:
    file = Path(path)
    lines = file.read_text(encoding="utf-8").splitlines() if file.exists() else []
    new_lines: list[str] = []
    replaced = False
    for line in lines:
        match = _LINE_RE.match(line)
        if match and match.group(1) == key:
            new_lines.append(f"{key}={value}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{key}={value}")
    file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def unset_env_value(path: str | Path, key: str) -> None:
    file = Path(path)
    if not file.exists():
        return
    lines = file.read_text(encoding="utf-8").splitlines()
    new_lines: list[str] = []
    for line in lines:
        match = _LINE_RE.match(line)
        if match and match.group(1) == key:
            continue
        new_lines.append(line)
    file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def mask(value: str) -> str:
    if not value:
        return "(unset)"
    if len(value) <= 4:
        return "****"
    return f"{value[:4]}****"

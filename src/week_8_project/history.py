"""Trwała historia rozmowy: zapis i odczyt listy wiadomości Pydantic AI jako JSON."""

import json
from pathlib import Path

from pydantic_ai import ModelMessage, ModelMessagesTypeAdapter
from pydantic_core import to_jsonable_python


def wczytaj_historie(plik: Path) -> list[ModelMessage]:
    """Zwraca zapisane wiadomości albo pustą listę, jeśli pliku jeszcze nie ma."""
    if not plik.exists():
        return []
    return ModelMessagesTypeAdapter.validate_python(json.loads(plik.read_text(encoding="utf-8")))


def zapisz_historie(plik: Path, historia: list[ModelMessage]) -> None:
    plik.parent.mkdir(parents=True, exist_ok=True)
    plik.write_text(
        json.dumps(to_jsonable_python(historia), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

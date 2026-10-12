"""Trwała historia rozmowy: zapis i odczyt listy wiadomości Pydantic AI jako JSON."""

import json
from pathlib import Path

from pydantic_ai import ModelMessage, ModelMessagesTypeAdapter, ModelRequest, ModelResponse, TextPart
from pydantic_ai.messages import UserPromptPart
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


def transkrypcja(historia: list[ModelMessage]) -> str:
    """Zamienia historię na zwykły tekst rozmowy: tylko pytania użytkownika i odpowiedzi tekstowe.

    Wywołania i wyniki narzędzi są pomijane, bo agent podsumowania nie ma tych narzędzi,
    więc nie wolno mu podawać wiadomości, które się do nich odwołują.
    """
    linie: list[str] = []
    for wiadomosc in historia:
        for czesc in wiadomosc.parts:
            if isinstance(wiadomosc, ModelRequest) and isinstance(czesc, UserPromptPart):
                if isinstance(czesc.content, str):
                    linie.append(f"Użytkownik: {czesc.content}")
            elif isinstance(wiadomosc, ModelResponse) and isinstance(czesc, TextPart):
                linie.append(f"Asystent: {czesc.content}")
    return "\n".join(linie)

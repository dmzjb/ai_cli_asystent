"""Trwała historia rozmowy: zapis i odczyt listy wiadomości Pydantic AI jako JSON."""

import json
from datetime import datetime
from pathlib import Path

from pydantic_ai import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
)
from pydantic_ai.messages import UserPromptPart
from pydantic_core import ValidationError, to_jsonable_python


class UszkodzonaHistoriaError(Exception):
    """Plik historii istnieje, ale nie da się go odczytać jako listy wiadomości."""


def wczytaj_historie(plik: Path) -> list[ModelMessage]:
    """Zwraca zapisane wiadomości albo pustą listę, jeśli pliku jeszcze nie ma.

    Rzuca UszkodzonaHistoriaError, gdy plik jest uszkodzony: pusty lub urwany, nie jest JSON-em,
    nie jest listą wiadomości albo nie jest poprawnym UTF-8.
    """
    if not plik.exists():
        return []
    try:
        return ModelMessagesTypeAdapter.validate_python(
            json.loads(plik.read_text(encoding="utf-8"))
        )
    except (json.JSONDecodeError, ValidationError, UnicodeDecodeError) as e:
        raise UszkodzonaHistoriaError(f"{plik}: {type(e).__name__}") from e


def odloz_uszkodzona_historie(plik: Path) -> Path:
    """Zmienia nazwę uszkodzonego pliku na kopię z datą (nic nie kasuje) i zwraca jej ścieżkę.

    Dzięki temu pierwszy zapis po starcie z pustą historią nie nadpisze uszkodzonych danych,
    z których da się jeszcze coś odzyskać ręcznie.
    """
    znacznik = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    kopia = plik.with_name(f"{plik.name}.uszkodzony-{znacznik}")
    numer = 1
    while kopia.exists():
        numer += 1
        kopia = plik.with_name(f"{plik.name}.uszkodzony-{znacznik}-{numer}")
    plik.rename(kopia)
    return kopia


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
            if isinstance(wiadomosc, ModelRequest) and isinstance(
                czesc, UserPromptPart
            ):
                if isinstance(czesc.content, str):
                    linie.append(f"Użytkownik: {czesc.content}")
            elif isinstance(wiadomosc, ModelResponse) and isinstance(czesc, TextPart):
                linie.append(f"Asystent: {czesc.content}")
    return "\n".join(linie)

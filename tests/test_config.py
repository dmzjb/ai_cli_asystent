from pathlib import Path

import pytest
from pydantic import ValidationError

from cli_ai_assistant.config import Settings
from cli_ai_assistant.models import PodsumowanieRozmowy


@pytest.fixture(autouse=True)
def bez_pliku_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Settings czyta ".env" względem bieżącego katalogu. Pusty katalog tymczasowy izoluje te testy
    # od prawdziwego pliku .env w projekcie.
    monkeypatch.chdir(tmp_path)



def test_brak_klucza_api_konczy_sie_bledem_walidacji(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(ValidationError, match="openrouter_api_key"):
        Settings()


def test_pusty_klucz_api_tez_jest_bledem(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    with pytest.raises(ValidationError):
        Settings()


def test_klucz_api_jest_czytany_ze_zmiennej_srodowiskowej(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "moj-klucz")

    assert Settings().openrouter_api_key == "moj-klucz"


def test_wartosci_domyslne(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.delenv("HISTORY_FILE", raising=False)
    monkeypatch.delenv("NOTES_FILE", raising=False)

    ustawienia = Settings()

    assert ustawienia.model == "anthropic/claude-haiku-4.5"
    assert ustawienia.notes_file == Path("data/notatki.txt")
    assert ustawienia.history_file == Path("data/historia.json")


def test_sciezki_mozna_nadpisac_zmienna_srodowiskowa(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("HISTORY_FILE", "inny/katalog/h.json")

    assert Settings().history_file == Path("inny/katalog/h.json")


# --- Model wyniku agenta podsumowania ---


def test_podsumowanie_wymaga_obu_pol():
    with pytest.raises(ValidationError):
        PodsumowanieRozmowy.model_validate({"tematy": ["x"]})


def test_pola_podsumowania_maja_opisy_dla_modelu_a_nie_placeholdery():
    schemat = PodsumowanieRozmowy.model_json_schema()

    for nazwa in ("tematy", "otwarte_sprawy"):
        opis = schemat["properties"][nazwa]["description"]
        assert len(opis) > 20, f"pole {nazwa} ma za krótki opis: {opis!r}"
        assert set(opis) != {"."}, f"pole {nazwa} ma placeholder zamiast opisu"

from pathlib import Path

import pytest
from pydantic_ai import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.messages import ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

import cli_ai_assistant.main as main_module
from cli_ai_assistant.agent import settings, summary_agent
from cli_ai_assistant.history import transkrypcja, zapisz_historie
from cli_ai_assistant.main import podsumuj, pokaz_podsumowanie
from cli_ai_assistant.models import PodsumowanieRozmowy


def _nic(*args: object, **kwargs: object) -> None:
    return None


def _rozmowa_z_narzedziem() -> list[ModelMessage]:
    return [
        ModelRequest(parts=[UserPromptPart(content="jaka pogoda w Krakowie?")]),
        ModelResponse(
            parts=[
                TextPart(content="Sprawdzę."),
                ToolCallPart("get_weather", {"city": "Kraków"}, "c1"),
            ]
        ),
        ModelRequest(parts=[ToolReturnPart("get_weather", "WYNIK-NARZEDZIA-21", "c1")]),
        ModelResponse(parts=[TextPart(content="W Krakowie jest 21 stopni.")]),
    ]


def _model_zwracajacy(tematy: list[str], otwarte: list[str], widziane: list[list[ModelMessage]]):
    """FunctionModel, który zapisuje, co dostał, i zwraca poprawny obiekt wyniku."""

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        widziane.append(messages)
        wyjscie = info.output_tools[0].name
        return ModelResponse(
            parts=[ToolCallPart(wyjscie, args={"tematy": tematy, "otwarte_sprawy": otwarte})]
        )

    return model


# --- transkrypcja: zwykły pytest, bez modelu ---


def test_transkrypcja_zawiera_pytania_i_odpowiedzi_w_kolejnosci():
    wynik = transkrypcja(_rozmowa_z_narzedziem())

    assert wynik.splitlines() == [
        "Użytkownik: jaka pogoda w Krakowie?",
        "Asystent: Sprawdzę.",
        "Asystent: W Krakowie jest 21 stopni.",
    ]


def test_transkrypcja_pomija_wywolania_i_wyniki_narzedzi():
    wynik = transkrypcja(_rozmowa_z_narzedziem())

    assert "get_weather" not in wynik
    assert "WYNIK-NARZEDZIA-21" not in wynik


def test_transkrypcja_pustej_historii_jest_pusta():
    assert transkrypcja([]) == ""


# --- podsumuj: summary_agent na FunctionModel ---


def test_podsumuj_wypisuje_wynik_i_zwraca_zuzycie(capsys: pytest.CaptureFixture[str]):
    widziane: list[list[ModelMessage]] = []
    model = _model_zwracajacy(["pogoda w Krakowie"], ["brak"], widziane)

    with summary_agent.override(model=FunctionModel(model)):
        zuzycie = podsumuj(_rozmowa_z_narzedziem())

    wydruk = capsys.readouterr().out
    assert zuzycie is not None
    assert zuzycie.requests == 1
    assert "pogoda w Krakowie" in wydruk
    assert "brak" in wydruk


def test_podsumuj_przekazuje_agentowi_transkrypcje_a_nie_historie_z_narzedziami():
    widziane: list[list[ModelMessage]] = []
    model = _model_zwracajacy(["x"], [], widziane)

    with summary_agent.override(model=FunctionModel(model)):
        podsumuj(_rozmowa_z_narzedziem())

    wiadomosci = widziane[0]
    prompty = [
        p.content
        for w in wiadomosci
        for p in w.parts
        if isinstance(p, UserPromptPart) and isinstance(p.content, str)
    ]
    assert prompty == [transkrypcja(_rozmowa_z_narzedziem())]
    assert not any(isinstance(p, ToolCallPart) for w in wiadomosci for p in w.parts)


def test_podsumuj_pustej_historii_nie_wola_modelu(capsys: pytest.CaptureFixture[str]):
    wywolania = 0

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal wywolania
        wywolania += 1
        return ModelResponse(parts=[TextPart("nie powinno sie wywolac")])

    with summary_agent.override(model=FunctionModel(model)):
        zuzycie = podsumuj([])

    assert zuzycie is None
    assert wywolania == 0
    assert "Brak rozmowy" in capsys.readouterr().out


def test_podsumuj_nie_wywala_programu_gdy_model_nie_daje_poprawnego_wyniku(
    capsys: pytest.CaptureFixture[str],
):
    # Czysty tekst zamiast obiektu: po wyczerpaniu retry framework rzuca UnexpectedModelBehavior,
    # a podsumuj ma go zamienić na komunikat (inaczej padłby cały CLI).
    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart("nie wiem")])

    with summary_agent.override(model=FunctionModel(model)):
        zuzycie = podsumuj(_rozmowa_z_narzedziem())

    assert zuzycie is None
    assert "Nie udało się przygotować podsumowania" in capsys.readouterr().out


def test_pokaz_podsumowanie_oznacza_puste_listy(capsys: pytest.CaptureFixture[str]):
    pokaz_podsumowanie(PodsumowanieRozmowy(tematy=[], otwarte_sprawy=[]))

    wydruk = capsys.readouterr().out
    assert wydruk.count("(brak)") == 2


# --- komenda /podsumuj w pętli main(): historia nietknięta, zużycie w /cost ---


def test_komenda_podsumuj_nie_zmienia_historii_i_liczy_sie_w_koszcie(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    plik_historii = tmp_path / "historia.json"
    zapisz_historie(plik_historii, _rozmowa_z_narzedziem())
    zawartosc_przed = plik_historii.read_text(encoding="utf-8")

    monkeypatch.setattr(settings, "history_file", plik_historii)
    monkeypatch.setattr(settings, "notes_file", tmp_path / "notatki.txt")
    # Bez tego logfire.configure() próbowałby konfigurować wysyłkę (a w pierwszym uruchomieniu
    # pytałby o projekt). Testy nie mogą nic wysyłać.
    monkeypatch.setattr(main_module.logfire, "configure", _nic)
    monkeypatch.setattr(main_module.logfire, "instrument_pydantic_ai", _nic)
    polecenia = iter(["/podsumuj", "/cost", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(polecenia))

    widziane: list[list[ModelMessage]] = []
    model = _model_zwracajacy(["pogoda w Krakowie"], [], widziane)
    with summary_agent.override(model=FunctionModel(model)):
        main_module.main()

    wydruk = capsys.readouterr().out
    assert "pogoda w Krakowie" in wydruk
    assert "requesty: 1" in wydruk
    assert plik_historii.read_text(encoding="utf-8") == zawartosc_przed

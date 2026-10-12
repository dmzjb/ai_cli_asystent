from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic_ai import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.messages import ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RunUsage

import cli_ai_assistant.main as main_module
from cli_ai_assistant.agent import agent, settings
from cli_ai_assistant.history import wczytaj_historie
from cli_ai_assistant.main import pokaz_koszt


def _nic(*args: object, **kwargs: object) -> None:
    return None


@dataclass
class Srodowisko:
    historia: Path
    notatki: Path
    wywolania_modelu: list[int]  # liczba wiadomości, którą widział model przy każdym wywołaniu

    def uruchom(
        self,
        monkeypatch: pytest.MonkeyPatch,
        polecenia: list[str],
        *,
        konczy_wyjatkiem: type[BaseException] | None = None,
    ) -> None:
        """Uruchamia main() z zaskryptowanym wejściem. Po wyczerpaniu poleceń input() rzuca
        EOFError (albo podany wyjątek), jak zamknięte wejście."""
        kolejka = iter(polecenia)
        wyjatek = konczy_wyjatkiem or EOFError

        def wejscie(_prompt: str = "") -> str:
            try:
                return next(kolejka)
            except StopIteration:
                raise wyjatek() from None

        monkeypatch.setattr("builtins.input", wejscie)
        with agent.override(model=FunctionModel(self._model)):
            main_module.main()

    def _model(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.wywolania_modelu.append(len(messages))
        ostatnie = messages[-1].parts
        zwroty = [p for p in ostatnie if isinstance(p, ToolReturnPart)]
        if zwroty:
            return ModelResponse(
                parts=[TextPart("Wynik: " + "; ".join(str(z.content) for z in zwroty))]
            )
        prompt = next(p.content for p in ostatnie if isinstance(p, UserPromptPart))
        assert isinstance(prompt, str)
        if "pogoda" in prompt:
            return ModelResponse(parts=[ToolCallPart("get_weather", {"city": "Kraków"})])
        if "zapisz" in prompt:
            return ModelResponse(parts=[ToolCallPart("save_note", {"note": "kupić mleko"})])
        return ModelResponse(parts=[TextPart(f"widzę {len(messages)} wiadomości")])


@pytest.fixture
def cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Srodowisko:
    historia, notatki = tmp_path / "historia.json", tmp_path / "notatki.txt"
    monkeypatch.setattr(settings, "history_file", historia)
    monkeypatch.setattr(settings, "notes_file", notatki)
    # Testy nie mogą nic konfigurować ani wysyłać do Logfire.
    monkeypatch.setattr(main_module.logfire, "configure", _nic)
    monkeypatch.setattr(main_module.logfire, "instrument_pydantic_ai", _nic)
    return Srodowisko(historia=historia, notatki=notatki, wywolania_modelu=[])


# --- pokaz_koszt ---


def test_pokaz_koszt_z_ceną(capsys: pytest.CaptureFixture[str]):
    suma = RunUsage(
        input_tokens=100, output_tokens=20, requests=2, tool_calls=1, cost=Decimal("0.0015")
    )

    pokaz_koszt(suma)

    wydruk = capsys.readouterr().out
    assert "100 wejście / 20 wyjście" in wydruk
    assert "requesty: 2" in wydruk and "wywołania narzędzi: 1" in wydruk
    assert "$0.001500" in wydruk


def test_pokaz_koszt_bez_ceny_mowi_o_braku_danych(capsys: pytest.CaptureFixture[str]):
    pokaz_koszt(RunUsage(input_tokens=1, output_tokens=1, requests=1))

    assert "brak danych o cenie" in capsys.readouterr().out


# --- Zwykła rozmowa i trwała historia ---


def test_tura_wypisuje_odpowiedz_i_zapisuje_historie(
    cli: Srodowisko, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    cli.uruchom(monkeypatch, ["cześć", "/exit"])

    assert "Bot: widzę 1 wiadomości" in capsys.readouterr().out
    assert len(wczytaj_historie(cli.historia)) == 2  # pytanie i odpowiedź


def test_historia_przezywa_restart_i_trafia_do_modelu(
    cli: Srodowisko, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    cli.uruchom(monkeypatch, ["cześć", "/exit"])
    capsys.readouterr()

    cli.uruchom(monkeypatch, ["a teraz?", "/exit"])  # "restart": main() od nowa

    wydruk = capsys.readouterr().out
    assert "Wiadomości w historii: 2" in wydruk
    assert "Bot: widzę 3 wiadomości" in wydruk  # 2 z dysku + nowe pytanie
    assert len(wczytaj_historie(cli.historia)) == 4


def test_pusty_input_jest_ignorowany_i_nie_wola_modelu(
    cli: Srodowisko, monkeypatch: pytest.MonkeyPatch
):
    cli.uruchom(monkeypatch, ["", "   ", "/exit"])

    assert cli.wywolania_modelu == []
    assert not cli.historia.exists()


def test_exit_konczy_petle_przed_kolejnymi_poleceniami(
    cli: Srodowisko, monkeypatch: pytest.MonkeyPatch
):
    cli.uruchom(monkeypatch, ["/exit", "cześć"])

    assert cli.wywolania_modelu == []


@pytest.mark.parametrize("wyjatek", [EOFError, KeyboardInterrupt])
def test_koniec_wejscia_i_ctrl_c_koncza_program_bez_tracebacku(
    cli: Srodowisko,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    wyjatek: type[BaseException],
):
    cli.uruchom(monkeypatch, [], konczy_wyjatkiem=wyjatek)

    assert "Do zobaczenia!" in capsys.readouterr().out


# --- /cost ---


def test_cost_zlicza_zuzycie_sesji(
    cli: Srodowisko, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    cli.uruchom(monkeypatch, ["/cost", "cześć", "/cost", "/exit"])

    wydruk = capsys.readouterr().out
    assert wydruk.index("requesty: 0") < wydruk.index("requesty: 1")


# --- Narzędzia wołane z poziomu pętli ---


def test_tura_z_pogoda_pokazuje_wynik_narzedzia(
    cli: Srodowisko, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    cli.uruchom(monkeypatch, ["jaka pogoda?", "/exit"])

    assert "Bot: Wynik: W mieście Kraków" in capsys.readouterr().out


def test_save_note_zapisuje_do_pliku_z_ustawien(
    cli: Srodowisko, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    cli.uruchom(monkeypatch, ["zapisz mleko", "/exit"])

    assert cli.notatki.read_text(encoding="utf-8") == "kupić mleko\n"
    assert "Zapisano notatkę." in capsys.readouterr().out


def test_blad_zapisu_notatki_nie_zamyka_programu_i_rozmowa_trwa(
    cli: Srodowisko,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    zablokowany = tmp_path / "to_jest_plik"
    zablokowany.write_text("x", encoding="utf-8")
    monkeypatch.setattr(settings, "notes_file", zablokowany / "notatki.txt")

    cli.uruchom(monkeypatch, ["zapisz mleko", "cześć", "/exit"])

    wydruk = capsys.readouterr().out
    assert "Bot: Wynik: Błąd zapisu notatki" in wydruk
    # Tura z narzędziem to 4 wiadomości (pytanie, wywołanie, wynik, odpowiedź) + nowe pytanie.
    # To też dowód, że po błędzie zapisu rozmowa dalej działa i ma pełny kontekst.
    assert "Bot: widzę 5 wiadomości" in wydruk


# --- Limit requestów na turę ---


def test_zwykla_tura_miesci_sie_w_limicie_jednego_requestu(
    cli: Srodowisko, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(main_module, "LIMIT_REQUESTOW_NA_TURE", 1)

    cli.uruchom(monkeypatch, ["cześć", "/exit"])

    assert "Bot: widzę 1 wiadomości" in capsys.readouterr().out


def test_przekroczenie_limitu_nie_wywala_programu_i_nie_zmienia_historii(
    cli: Srodowisko, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    cli.uruchom(monkeypatch, ["cześć", "/exit"])
    historia_przed = cli.historia.read_text(encoding="utf-8")
    capsys.readouterr()

    # Tura z narzędziem to min. 2 requesty, więc limit 1 ją przerywa.
    monkeypatch.setattr(main_module, "LIMIT_REQUESTOW_NA_TURE", 1)
    cli.uruchom(monkeypatch, ["jaka pogoda?", "/exit"])

    assert "Przekroczono limit" in capsys.readouterr().out
    assert cli.historia.read_text(encoding="utf-8") == historia_przed


def test_przerwana_tura_nie_trafia_do_kontekstu_kolejnych_pytan(
    cli: Srodowisko, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    cli.uruchom(monkeypatch, ["cześć", "/exit"])
    monkeypatch.setattr(main_module, "LIMIT_REQUESTOW_NA_TURE", 1)
    cli.uruchom(monkeypatch, ["jaka pogoda?", "/exit"])  # przerwana limitem
    monkeypatch.setattr(main_module, "LIMIT_REQUESTOW_NA_TURE", 10)
    capsys.readouterr()

    cli.uruchom(monkeypatch, ["dalej", "/exit"])

    # 2 wiadomości z pierwszej tury + nowe pytanie (nic z przerwanej tury)
    assert "Bot: widzę 3 wiadomości" in capsys.readouterr().out


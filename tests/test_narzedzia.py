from pathlib import Path
from typing import Any

import pytest
from pydantic_ai import (
    ModelMessage,
    ModelResponse,
    ModelRetry,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import RetryPromptPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from cli_ai_assistant.agent import (
    INSTRUCTIONS,
    AsystentDeps,
    agent,
    calculate,
    get_weather,
)


def _deps(tmp_path: Path) -> AsystentDeps:
    return AsystentDeps(notes_file=tmp_path / "notatki.txt")


def _model_wolajacy(*wywolania: tuple[str, dict[str, Any]]):
    """Scenariusz: model prosi o podane narzędzia (naraz), a potem streszcza ich wyniki."""

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        zwroty = [p for p in messages[-1].parts if isinstance(p, ToolReturnPart)]
        if zwroty:
            return ModelResponse(
                parts=[TextPart("; ".join(f"{z.tool_name}={z.content}" for z in zwroty))]
            )
        return ModelResponse(parts=[ToolCallPart(nazwa, args=args) for nazwa, args in wywolania])

    return model


# --- Definicje narzędzi widziane przez model ---


def test_narzedzia_maja_nazwy_z_instrukcji_i_niepuste_opisy(tmp_path: Path):
    widziane: dict[str, str | None] = {}

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        for narzedzie in info.function_tools:
            widziane[narzedzie.name] = narzedzie.description
        return ModelResponse(parts=[TextPart("ok")])

    with agent.override(model=FunctionModel(model)):
        agent.run_sync("x", deps=_deps(tmp_path))

    assert set(widziane) == {"get_weather", "calculate", "save_note"}
    for nazwa, opis in widziane.items():
        assert opis is not None and opis.strip(), f"narzędzie {nazwa} nie ma opisu"
        assert nazwa in INSTRUCTIONS, f"instrukcje nie wspominają narzędzia {nazwa}"


# --- get_weather i calculate wołane bezpośrednio (zwykłe funkcje) ---


def test_get_weather_zawiera_nazwe_miasta():
    assert "Kraków" in get_weather("Kraków")


@pytest.mark.parametrize(
    ("wyrazenie", "oczekiwany"),
    [("2 + 2", "4"), ("7 / 2", "3.5"), ("2 ** 10", "1024")],
)
def test_calculate_zwraca_wynik_jako_tekst(wyrazenie: str, oczekiwany: str):
    assert calculate(wyrazenie) == oczekiwany


def test_calculate_dzielenie_przez_zero_zwraca_tekst_a_nie_wyjatek():
    wynik = calculate("10 / 0")

    assert "dzielenie przez zero" in wynik


@pytest.mark.parametrize("wyrazenie", ["2 +", "__import__('os')", "x + 1"])
def test_calculate_zle_wyrazenie_rzuca_modelretry(wyrazenie: str):
    with pytest.raises(ModelRetry, match="Niepoprawne wyrażenie"):
        calculate(wyrazenie)


# --- Narzędzia w agencie, na FunctionModel ---


def test_agent_zwraca_wynik_calculate(tmp_path: Path):
    with agent.override(model=FunctionModel(_model_wolajacy(("calculate", {"expression": "2 + 2"})))):
        wynik = agent.run_sync("ile to 2+2", deps=_deps(tmp_path))

    assert wynik.output == "calculate=4"


def test_modelretry_naprawia_zle_wyrazenie(tmp_path: Path):
    komunikaty: list[str] = []

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        czesci = messages[-1].parts
        zwrot = next((p for p in czesci if isinstance(p, ToolReturnPart)), None)
        retry = next((p for p in czesci if isinstance(p, RetryPromptPart)), None)
        if zwrot is not None:
            return ModelResponse(parts=[TextPart(f"Wynik: {zwrot.content}")])
        if retry is not None:
            komunikaty.append(retry.model_response())
            return ModelResponse(parts=[ToolCallPart("calculate", args={"expression": "2 + 2"})])
        return ModelResponse(parts=[ToolCallPart("calculate", args={"expression": "2 +"})])

    with agent.override(model=FunctionModel(model)):
        wynik = agent.run_sync("policz", deps=_deps(tmp_path))

    assert wynik.output == "Wynik: 4"
    assert len(komunikaty) == 1
    assert "Niepoprawne wyrażenie" in komunikaty[0]


@pytest.mark.parametrize("wyrazenie", ["2 +", "__import__('os')"])
def test_uporczywie_zle_wyrazenie_wyczerpuje_retry(tmp_path: Path, wyrazenie: str):
    scenariusz = _model_wolajacy(("calculate", {"expression": wyrazenie}))
    with (
        agent.override(model=FunctionModel(scenariusz)),
        pytest.raises(UnexpectedModelBehavior, match="exceeded max retries"),
    ):
        agent.run_sync("policz", deps=_deps(tmp_path))


def test_dzielenie_przez_zero_nie_wywala_runa_a_model_dostaje_tekst(tmp_path: Path):
    with agent.override(model=FunctionModel(_model_wolajacy(("calculate", {"expression": "10 / 0"})))):
        wynik = agent.run_sync("ile to 10/0", deps=_deps(tmp_path))

    assert "dzielenie przez zero" in wynik.output


def test_dwa_rozne_narzedzia_w_jednej_turze(tmp_path: Path):
    scenariusz = _model_wolajacy(
        ("get_weather", {"city": "Kraków"}),
        ("calculate", {"expression": "3450 * 17 / 100"}),
    )
    with agent.override(model=FunctionModel(scenariusz)):
        wynik = agent.run_sync("pogoda i rachunek", deps=_deps(tmp_path))

    assert "get_weather=" in wynik.output and "Kraków" in wynik.output
    assert "calculate=586.5" in wynik.output


# --- TestModel: sprawdza instalację narzędzi, nie decyzje modelu ---


def test_testmodel_wola_narzedzia_z_deps_bez_bledu(tmp_path: Path):
    deps = _deps(tmp_path)

    # call_tools zawęża TestModel; domyślnie wołałby też calculate z losowym tekstem,
    # który słusznie kończy się ModelRetry.
    with agent.override(model=TestModel(call_tools=["get_weather", "save_note"])):
        agent.run_sync("cokolwiek", deps=deps)

    assert len(deps.notes_file.read_text(encoding="utf-8").splitlines()) == 1


# --- Znana luka: błąd zapisu notatki wywala cały run (patrz raport) ---


@pytest.mark.xfail(
    strict=True,
    raises=OSError,
    reason="save_note nie obsługuje OSError: błąd dysku przerywa run zamiast trafić do modelu jako tekst",
)
def test_blad_zapisu_notatki_nie_wywala_runa(tmp_path: Path):
    zablokowany = tmp_path / "to_jest_plik"
    zablokowany.write_text("x", encoding="utf-8")
    deps = AsystentDeps(notes_file=zablokowany / "notatki.txt")  # katalog nadrzędny to zwykły plik

    with agent.override(model=FunctionModel(_model_wolajacy(("save_note", {"note": "x"})))):
        wynik = agent.run_sync("zapisz", deps=deps)

    assert "Błąd" in wynik.output

from pathlib import Path

from pydantic_ai import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from cli_ai_assistant.agent import AsystentDeps, agent
from cli_ai_assistant.logic import save_note_function

# --- Logika zapisu: zwykły pytest, bez agenta, bez modelu ---


def test_tworzy_brakujace_katalogi_i_plik(tmp_path: Path):
    plik = tmp_path / "data" / "podkatalog" / "notatki.txt"

    save_note_function(plik, "Kupić mleko")

    assert plik.read_text(encoding="utf-8") == "Kupić mleko\n"


def test_dopisuje_zamiast_nadpisywac(tmp_path: Path):
    plik = tmp_path / "notatki.txt"

    save_note_function(plik, "pierwsza")
    save_note_function(plik, "druga")

    assert plik.read_text(encoding="utf-8") == "pierwsza\ndruga\n"


def test_zachowuje_polskie_znaki(tmp_path: Path):
    plik = tmp_path / "notatki.txt"

    save_note_function(plik, "Zażółć gęślą jaźń")

    assert plik.read_text(encoding="utf-8") == "Zażółć gęślą jaźń\n"


# --- Narzędzie save_note w agencie: deps ze ścieżką do pliku, "model" pisze FunctionModel ---


def _model_wolajacy_save_note(*notatki: str):
    """Scenariusz: najpierw model prosi o save_note (jedno wywołanie na notatkę), potem odpowiada."""

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        zwroty = [p for p in messages[-1].parts if isinstance(p, ToolReturnPart)]
        if zwroty:
            return ModelResponse(parts=[TextPart(f"Zapisano {len(zwroty)}")])
        return ModelResponse(
            parts=[ToolCallPart("save_note", args={"note": n}) for n in notatki]
        )

    return model


def test_agent_zapisuje_notatke_do_pliku_z_deps(tmp_path: Path):
    plik = tmp_path / "notatki.txt"
    deps = AsystentDeps(notes_file=plik)

    with agent.override(model=FunctionModel(_model_wolajacy_save_note("Jutro lekarz o 15:00"))):
        wynik = agent.run_sync("zapisz, że jutro lekarz o 15:00", deps=deps)

    assert plik.read_text(encoding="utf-8") == "Jutro lekarz o 15:00\n"
    assert wynik.output == "Zapisano 1"


def test_dwa_zapisy_w_jednej_turze_nie_gubia_notatek(tmp_path: Path):
    # Narzędzia w jednej turze wykonują się współbieżnie w wątkach (dzień 3). Sam tryb dopisywania
    # nie wystarcza (na Windows ~60% prób gubiło lub psuło notatkę), dlatego save_note_function
    # używa blokady. Ten test pilnuje, żeby jej nikt nie usunął.
    plik = tmp_path / "notatki.txt"
    deps = AsystentDeps(notes_file=plik)

    with agent.override(model=FunctionModel(_model_wolajacy_save_note("pierwsza", "druga"))):
        agent.run_sync("zapisz dwie notatki", deps=deps)

    linie = plik.read_text(encoding="utf-8").splitlines()
    assert sorted(linie) == ["druga", "pierwsza"]


def test_rozne_deps_zapisuja_do_roznych_plikow(tmp_path: Path):
    # To, czego nie dało się czysto zrobić w wersji bez frameworka: izolacja przez deps,
    # bez monkeypatchowania Path.home().
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"

    with agent.override(model=FunctionModel(_model_wolajacy_save_note("do A"))):
        agent.run_sync("x", deps=AsystentDeps(notes_file=a))
    with agent.override(model=FunctionModel(_model_wolajacy_save_note("do B"))):
        agent.run_sync("x", deps=AsystentDeps(notes_file=b))

    assert a.read_text(encoding="utf-8") == "do A\n"
    assert b.read_text(encoding="utf-8") == "do B\n"

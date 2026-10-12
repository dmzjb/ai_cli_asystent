from pathlib import Path

from pydantic_ai import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.messages import ToolReturnPart, UserPromptPart

from cli_ai_assistant.history import wczytaj_historie, zapisz_historie


def _rozmowa() -> list[ModelMessage]:
    return [
        ModelRequest(parts=[UserPromptPart(content="Zapisz: zażółć gęślą jaźń")]),
        ModelResponse(
            parts=[
                TextPart(content="Zapisuję."),
                ToolCallPart("save_note", {"note": "zażółć gęślą jaźń"}, "c1"),
            ]
        ),
        ModelRequest(parts=[ToolReturnPart("save_note", "Zapisano notatkę.", "c1")]),
        ModelResponse(parts=[TextPart(content="Gotowe.")]),
    ]


def test_wczytanie_nieistniejacego_pliku_daje_pusta_liste(tmp_path: Path):
    assert wczytaj_historie(tmp_path / "nie_ma.json") == []


def test_zapis_i_odczyt_zachowuja_wiadomosci_bez_zmian(tmp_path: Path):
    plik = tmp_path / "historia.json"
    oryginal = _rozmowa()

    zapisz_historie(plik, oryginal)

    assert wczytaj_historie(plik) == oryginal


def test_odczyt_zachowuje_typy_czesci_wiadomosci(tmp_path: Path):
    plik = tmp_path / "historia.json"
    zapisz_historie(plik, _rozmowa())

    wczytana = wczytaj_historie(plik)

    rodzaje = [type(czesc).__name__ for w in wczytana for czesc in w.parts]
    assert rodzaje == ["UserPromptPart", "TextPart", "ToolCallPart", "ToolReturnPart", "TextPart"]


def test_zapis_tworzy_brakujace_katalogi(tmp_path: Path):
    plik = tmp_path / "data" / "glebiej" / "historia.json"

    zapisz_historie(plik, _rozmowa())

    assert plik.exists()


def test_zapis_nadpisuje_poprzednia_zawartosc_zamiast_dopisywac(tmp_path: Path):
    plik = tmp_path / "historia.json"
    zapisz_historie(plik, _rozmowa()[:2])

    zapisz_historie(plik, _rozmowa())

    assert len(wczytaj_historie(plik)) == 4


def test_polskie_znaki_sa_czytelne_w_pliku_a_nie_zakodowane(tmp_path: Path):
    plik = tmp_path / "historia.json"

    zapisz_historie(plik, _rozmowa())

    tresc = plik.read_text(encoding="utf-8")
    assert "zażółć gęślą jaźń" in tresc
    assert "\\u" not in tresc


def test_zapis_pustej_historii_daje_pusta_liste_po_odczycie(tmp_path: Path):
    plik = tmp_path / "historia.json"

    zapisz_historie(plik, [])

    assert wczytaj_historie(plik) == []

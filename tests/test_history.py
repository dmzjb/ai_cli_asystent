import re
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

from cli_ai_assistant.history import (
    UszkodzonaHistoriaError,
    odloz_uszkodzona_historie,
    wczytaj_historie,
    zapisz_historie,
)


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
    assert rodzaje == [
        "UserPromptPart",
        "TextPart",
        "ToolCallPart",
        "ToolReturnPart",
        "TextPart",
    ]


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


# --- Uszkodzony plik historii ---

USZKODZONE = [
    pytest.param(b"", id="pusty plik"),
    pytest.param(b'[{"parts": [', id="urwany JSON"),
    pytest.param(b"to nie jest json", id="nie JSON"),
    pytest.param(b'{"a": 1}', id="JSON, ale nie lista"),
    pytest.param(b"[1, 2, 3]", id="lista liczb zamiast wiadomosci"),
    pytest.param(b"[{}]", id="lista pustych obiektow"),
    pytest.param(b"\xff\xfe\x00\x80bad", id="nie UTF-8"),
]


@pytest.mark.parametrize("zawartosc", USZKODZONE)
def test_uszkodzony_plik_rzuca_uszkodzona_historie_error(
    tmp_path: Path, zawartosc: bytes
):
    plik = tmp_path / "historia.json"
    plik.write_bytes(zawartosc)

    with pytest.raises(UszkodzonaHistoriaError, match="historia.json"):
        wczytaj_historie(plik)


def test_poprawna_pusta_lista_nie_jest_uszkodzeniem(tmp_path: Path):
    plik = tmp_path / "historia.json"
    plik.write_text("[]", encoding="utf-8")

    assert wczytaj_historie(plik) == []


def test_odlozenie_zachowuje_zawartosc_i_usuwa_oryginalna_nazwe(tmp_path: Path):
    plik = tmp_path / "historia.json"
    plik.write_bytes(b"to nie jest json")

    kopia = odloz_uszkodzona_historie(plik)

    assert not plik.exists()
    assert kopia.read_bytes() == b"to nie jest json"
    assert kopia.parent == tmp_path
    assert re.fullmatch(r"historia\.json\.uszkodzony-\d{8}-\d{6}", kopia.name)


def test_dwa_uszkodzenia_w_tej_samej_sekundzie_nie_nadpisuja_sie(tmp_path: Path):
    plik = tmp_path / "historia.json"
    plik.write_bytes(b"pierwszy")
    pierwsza = odloz_uszkodzona_historie(plik)
    plik.write_bytes(b"drugi")

    druga = odloz_uszkodzona_historie(plik)

    assert pierwsza != druga
    assert pierwsza.read_bytes() == b"pierwszy"
    assert druga.read_bytes() == b"drugi"

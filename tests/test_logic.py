import ast

import pytest

from cli_ai_assistant.logic import safe_exec


def policz(wyrazenie: str) -> float:
    return safe_exec(ast.parse(wyrazenie, mode="eval"))


@pytest.mark.parametrize(
    ("wyrazenie", "oczekiwany"),
    [
        ("2 + 2", 4),
        ("2 + 3 * 4", 14),  # priorytet operatorów
        ("(2 + 3) * 4", 20),  # nawiasy
        ("((1 + 2) * (3 + 4)) / 7", 3),
        ("-5 + 3", -2),  # minus unarny
        ("5 * -2", -10),
        ("7 / 2", 3.5),
        ("2 ** 10", 1024),
        ("10 % 3", 1),
        ("3450 * 17 / 100", 586.5),
    ],
)
def test_liczy_poprawne_wyrazenia(wyrazenie: str, oczekiwany: float):
    assert policz(wyrazenie) == pytest.approx(oczekiwany)


@pytest.mark.parametrize("wyrazenie", ["5 / 0", "10 % 0"])
def test_dzielenie_przez_zero_rzuca_zerodivisionerror(wyrazenie: str):
    with pytest.raises(ZeroDivisionError):
        policz(wyrazenie)


# Bezpieczeństwo: wyrażenie pisze model, więc nigdy nie może wykonać dowolnego kodu.
@pytest.mark.parametrize(
    "wyrazenie",
    [
        "__import__('os')",  # wywołanie funkcji
        "x + 1",  # zmienna
        "().__class__",  # dostęp do atrybutu (ucieczka przez dundery)
        "[1, 2]",  # lista
        "'a' * 3",  # string zamiast liczby
        "1j",  # liczba zespolona
    ],
)
def test_odrzuca_elementy_spoza_bezpiecznego_podzbioru(wyrazenie: str):
    with pytest.raises(ValueError, match="niedozwolony"):
        policz(wyrazenie)


@pytest.mark.parametrize("wyrazenie", ["7 // 2", "2 << 3", "+5"])
def test_odrzuca_nieobslugiwane_operatory(wyrazenie: str):
    with pytest.raises(ValueError, match="niedozwolony operator"):
        policz(wyrazenie)


@pytest.mark.parametrize("wyrazenie", ["2 +", "(1 + 2", ""])
def test_bledna_skladnia_rzuca_syntaxerror(wyrazenie: str):
    with pytest.raises(SyntaxError):
        policz(wyrazenie)

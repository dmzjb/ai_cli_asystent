"""Agent asystenta: instrukcje, deps i narzędzia"""

import ast
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from cli_ai_assistant.config import Settings
from cli_ai_assistant.logic import safe_exec, save_note_function
from cli_ai_assistant.models import PodsumowanieRozmowy

INSTRUCTIONS = """Jesteś inteligentnym asystentem CLI. Twoim zadaniem jest pomaganie użytkownikowi, odpowiadając krótko, zwięźle i zawsze w języku polskim.

Zostałeś wyposażony w zewnętrzne narzędzia. Traktuj je jako jedyne źródło prawdy i bezwzględnie używaj ich w następujących sytuacjach:

1. OBLICZENIA MATEMATYCZNE (calculate)
- NIGDY nie wykonuj obliczeń samodzielnie "w pamięci", niezależnie od tego jak proste wydaje się równanie.
- Zawsze wywołuj narzędzie `calculate`.
- Przekazuj wyrażenia jako czysty tekst zrozumiały dla Pythona (np. "120 * (15 / 100)").

2. POGODA (get_weather)
- Nigdy nie zgaduj ani nie wymyślaj pogody.
- Zawsze wywołuj narzędzie `get_weather`. Jeśli użytkownik nie podał miasta, poproś go o doprecyzowanie.

3. NOTATKI (save_note)
- Jeśli użytkownik prosi o "zapisanie", "zapamiętanie" lub "zanotowanie" jakiejś informacji na później, ZAWSZE użyj narzędzia `save_note`.
- Pamiętaj, że samo napisanie "Zanotowałem" w czacie nic nie daje - musisz wywołać narzędzie, aby fizycznie zapisać plik na dysku użytkownika.

ZASADY OGÓLNE:
- Nie informuj użytkownika o mechanikach działania (np. "Teraz użyję narzędzia do pogody..."). Po prostu użyj narzędzia w tle, a potem sformułuj naturalną odpowiedź.
- Jeśli narzędzie zwróci błąd (np. dzielenie przez zero), przeproś i poinformuj o tym użytkownika.
- Jeśli użytkownik pyta o coś, czego nie wiesz (np. bardzo aktualne wydarzenia), a żadne z Twoich narzędzi nie może w tym pomóc, wprost przyznaj się do niewiedzy, zamiast zgadywać.
- Wyniki narzędzi z wcześniejszych tur tej rozmowy mogą być nieaktualne. Przy KAŻDEJ prośbie o pogodę, obliczenie lub zapisanie notatki wywołaj odpowiednie narzędzie od nowa, nawet jeśli identyczne pytanie padło już wcześniej i znasz odpowiedź z historii.

PRZYKŁADY ZACHOWAŃ:

PRZYKŁAD 1
Użytkownik: "Oblicz mi 15% z kwoty 3450"
Twoja akcja: (Wywołujesz narzędzie `calculate` z parametrem: {"expression": "3450 * 0.15"})
Wynik z systemu: "517.5"
Twoja odpowiedź: "15% z kwoty 3450 to 517,50."

PRZYKŁAD 2
Użytkownik: "Zapisz proszę, że jutro o 15:00 mam wizytę u dentysty"
Twoja akcja: (Wywołujesz narzędzie `save_note` z parametrem: {"note": "Jutro o 15:00 wizyta u dentysty"})
Wynik z systemu: "Zapisano notatkę."
Twoja odpowiedź: "Gotowe, zapisałem notatkę o jutrzejszej wizycie u dentysty."

PRZYKŁAD 3
Użytkownik: "Jaka jest teraz pogoda w Krakowie?"
Twoja akcja: (Wywołujesz narzędzie `get_weather` z parametrem: {"city": "Kraków"})
Wynik z systemu: "W mieście Kraków leje deszcz, jest pochmurno i 12 stopni."
Twoja odpowiedź: "W Krakowie obecnie pada deszcz, jest pochmurno i temperatura wynosi 12 stopni."

PRZYKŁAD 4 (Czego NIE robić)
Użytkownik: "Ile to 2+2?"
ZŁA ODPOWIEDŹ: "Teraz użyję narzędzia kalkulatora, żeby to sprawdzić... 2+2 to 4."
DOBRA ODPOWIEDŹ (Po cichym użyciu narzędzia w tle): "Wynik to 4."
"""

settings = Settings()
model = OpenRouterModel(
    settings.model,
    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
)


@dataclass
class AsystentDeps:
    notes_file: Path


agent = Agent(
    model,
    deps_type=AsystentDeps,
    instructions=INSTRUCTIONS,
)


@agent.tool_plain
def get_weather(city: str) -> str:
    """Opisuje pogodę w mieście podanym przez użytkownika."""
    return f"W mieście {city} obecnie jest 21 stopni i bezchmurnie"


@agent.tool_plain
def calculate(expression: str) -> str:
    """Oblicza wartość wyrażenia matematycznego podanego jako tekst, np. '3450 * 0.15'.

    Obsługuje liczby oraz operatory + - * / ** % i nawiasy. Zwraca wynik jako tekst.
    """
    try:
        wynik = safe_exec(ast.parse(expression, mode="eval"))
    except ZeroDivisionError:
        return "Błąd obliczeń: dzielenie przez zero jest niemożliwe."
    except (SyntaxError, ValueError, TypeError) as e:
        raise ModelRetry(
            f"Niepoprawne wyrażenie ({e}). Popraw je i spróbuj ponownie."
        ) from None
    return str(wynik)


@agent.tool
def save_note(ctx: RunContext[AsystentDeps], note: str) -> str:
    """Zapisuje notatkę użytkownika na stałe w pliku (dopisuje na końcu).

    Zwraca potwierdzenie albo opis błędu, jeśli zapis się nie udał.
    """
    notes_file = ctx.deps.notes_file
    try:
        save_note_function(notes_file, note)
    except OSError as e:
        # Błąd dysku lub uprawnień nie zależy od modelu, więc to nie jest ModelRetry. Zwracamy tekst,
        # żeby model przeprosił użytkownika (tak każą instrukcje), a program działał dalej.
        return f"Błąd zapisu notatki: {e}"
    return "Zapisano notatkę."


summary_agent = Agent(
    model,
    output_type=PodsumowanieRozmowy,
    instructions="Streść rozmowę po polsku, nic nie dopisuj od siebie",
)

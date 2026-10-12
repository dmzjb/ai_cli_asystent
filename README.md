# CLI AI Assistant

Konsolowy asystent AI napisany w [Pydantic AI](https://ai.pydantic.dev). Rozmawia w terminalu,
samodzielnie wybiera spośród trzech narzędzi, pamięta rozmowę między uruchomieniami, potrafi
podsumować ją jako ustrukturyzowany obiekt i zostawia pełny ślad każdego przebiegu w Logfire.

## Co potrafi

- **Rozmowa z pamięcią zapisywaną na dysku.** Historia ląduje w pliku JSON po każdej turze, więc
  przeżywa restart programu.
- **Trzy narzędzia**, z których model korzysta sam (także kilku naraz w jednej turze):
  - `get_weather(city)`: pogoda dla miasta (dane **fikcyjne**, stała odpowiedź),
  - `calculate(expression)`: kalkulator oparty na parserze `ast` (`+ - * / ** %`, nawiasy, minus
    unarny), bez `eval()`, więc model nie wykona dowolnego kodu Pythona,
  - `save_note(note)`: dopisuje notatkę do pliku tekstowego.
- **`/podsumuj`**: osobny agent zwraca podsumowanie rozmowy jako obiekt Pydantic (tematy i otwarte
  sprawy), a nie luźny tekst.
- **`/cost`**: tokeny, liczba requestów i wywołań narzędzi oraz koszt sesji (gdy dostawca podaje
  cenę; OpenRouter podaje).
- **Bezpieczniki**: limit 10 requestów do modelu na jedną turę, czytelne komunikaty zamiast
  tracebacków przy błędach.
- **Obserwowalność**: każdy przebieg widoczny jako trace w [Logfire](https://logfire.pydantic.dev)
  (prompty, wywołania narzędzi, tokeny, czasy). Opcjonalnie.

## Stack

Python 3.14, Pydantic AI, OpenRouter (domyślnie Claude Haiku 4.5), pydantic-settings, Logfire,
pytest, [uv](https://docs.astral.sh/uv/).

## Uruchomienie

Wymagany [uv](https://docs.astral.sh/uv/) (zarządza też wersją Pythona).

1. Zainstaluj zależności:
   ```bash
   uv sync
   ```
2. Utwórz plik `.env` w katalogu głównym z kluczem OpenRouter (klucz zdobędziesz na
   [openrouter.ai/keys](https://openrouter.ai/keys), plik `.env` jest w `.gitignore`):
   ```
   OPENROUTER_API_KEY=twój-klucz
   ```
3. Zdecyduj o Logfire (patrz niżej). Najprościej wyłączyć wysyłkę:

   PowerShell:
   ```powershell
   $env:LOGFIRE_SEND_TO_LOGFIRE = "false"
   ```
   bash:
   ```bash
   export LOGFIRE_SEND_TO_LOGFIRE=false
   ```
4. Uruchom:
   ```bash
   uv run week-8-project
   ```

### Logfire (opcjonalnie)

Program zawsze konfiguruje Logfire przy starcie. **Bez zmiennej `LOGFIRE_SEND_TO_LOGFIRE=false`
przy pierwszym uruchomieniu zapyta o logowanie i wybór projektu.** Zmienna musi być w środowisku
powłoki, a nie w `.env` (Logfire nie czyta tego pliku). Żeby włączyć śledzenie:

```bash
uv run logfire auth
uv run logfire projects use NAZWA_PROJEKTU --org NAZWA_ORGANIZACJI
```

Konto musi mieć organizację i projekt (załóż je w przeglądarce). Dane logowania trafiają do
katalogu `.logfire/`, który jest w `.gitignore`. Uwaga: do Logfire wysyłane są pełne prompty i wyniki
narzędzi, czyli także treść rozmowy i notatek.

## Konfiguracja

Zmienne środowiskowe lub wpisy w `.env`:

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `OPENROUTER_API_KEY` | brak (wymagana) | klucz API OpenRouter; brak lub pusty kończy się błędem walidacji przy starcie |
| `MODEL` | `anthropic/claude-haiku-4.5` | nazwa modelu w katalogu OpenRouter |
| `NOTES_FILE` | `data/notatki.txt` | plik, do którego `save_note` dopisuje notatki |
| `HISTORY_FILE` | `data/historia.json` | plik z historią rozmowy |

Katalog `data/` jest w `.gitignore`.

## Komendy w czacie

| Komenda | Działanie |
|---|---|
| `/podsumuj` | podsumowanie rozmowy: tematy i otwarte sprawy (nie zmienia historii) |
| `/cost` | zużycie i koszt bieżącej sesji |
| `/exit` | koniec programu (Ctrl+C lub koniec wejścia też kończą go bez błędu) |

Przykład: `jaka pogoda w Krakowie i ile to 17% z 3450?` wywoła dwa narzędzia w jednej turze.

## Architektura

```
src/cli_ai_assistant/
├── config.py    ustawienia (klucz, model, ścieżki plików) przez pydantic-settings
├── logic.py     logika narzędzi bez frameworka: bezpieczny kalkulator, zapis notatki
├── agent.py     instrukcje, zależności (deps), trzy narzędzia, agent podsumowania
├── models.py    PodsumowanieRozmowy: wynik agenta podsumowania
├── history.py   zapis i odczyt historii (JSON), budowa transkrypcji rozmowy
└── main.py      pętla CLI, komendy, limity, koszt, Logfire
tests/           testy każdego modułu
```

## Decyzje projektowe

- **Ścieżka do notatek przez `deps`.** `AsystentDeps` niesie ścieżkę pliku, więc narzędzie
  `save_note` nie zna globalnej lokalizacji, a testy zapisują do katalogu tymczasowego.
- **Narzędzia z jednej tury wykonują się współbieżnie.** Dwa równoległe zapisy do jednego pliku
  potrafiły się nawzajem uszkodzić (na Windows dopisywanie przez osobne uchwyty nie jest atomowe),
  dlatego zapis notatki jest chroniony blokadą.
- **Dwa rodzaje błędów narzędzi.** Zły argument od modelu (np. niepoprawne wyrażenie) kończy się
  `ModelRetry`, bo model może go poprawić. Błędy, których model nie naprawi (dzielenie przez zero,
  błąd zapisu na dysk), wracają do niego jako zwykły tekst, żeby przeprosił użytkownika, a program
  działał dalej.
- **Historia a narzędzia.** Trwała historia sprawia, że model skłonny jest odpowiadać z pamięci
  zamiast ponownie pytać narzędzie, więc instrukcje każą wołać narzędzia od nowa przy każdej prośbie.
- **Podsumowanie z transkrypcji, nie z historii.** Agent podsumowania nie ma narzędzi, więc
  dostaje wyłącznie tekst pytań i odpowiedzi (bez wywołań i wyników narzędzi). Jego wynik nie
  trafia do historii rozmowy.
- **Limit requestów na turę, nie na sesję.** Tura z narzędziem to minimum dwa requesty do modelu
  (prośba o narzędzie i odpowiedź po jego wyniku), dlatego limit wynosi 10.

## Testy

```bash
uv run pytest
```

Testy nie wymagają klucza API ani sieci. Model jest podmieniany na `FunctionModel` (scenariusze
pisane ręcznie) i `TestModel`, atrapa klucza jest ustawiana przed importem, a prawdziwe wywołania
modelu są zablokowane (`ALLOW_MODEL_REQUESTS = False`). Pokrywają: logikę narzędzi (w tym
odrzucanie niebezpiecznych wyrażeń), narzędzia w agencie (retry, błędy, kilka narzędzi naraz),
zapis i odczyt historii, pętlę CLI (restart z historią, limit, `/cost`, `/podsumuj`), konfigurację.

## Znane ograniczenia

- Pogoda jest fikcyjna (stała odpowiedź), to demonstracja narzędzia, a nie integracja z API.
- Kalkulator dopuszcza `**` bez limitu wielkości wykładnika, więc bardzo duża potęga może zająć
  procesor na długo.
- Uszkodzony plik historii zatrzymuje start programu (trzeba go usunąć).
- Cała historia jest wysyłana do modelu przy każdym żądaniu, więc koszt kolejnych tur rośnie
  z długością rozmowy (brak przycinania i limitu kosztu na całą sesję). `/podsumuj` wysyła całą
  transkrypcję.

# CLI AI Assistant

[English](#english) | [Polski](#polski)

---

## English

A console AI assistant built with [Pydantic AI](https://ai.pydantic.dev). It chats in the terminal,
picks among three tools on its own, remembers the conversation between runs, can summarize it as a
structured object, and leaves a full trace of every run in Logfire.

### Features

- **Conversation memory stored on disk.** The history is saved to a JSON file after every turn, so
  it survives a restart.
- **Three tools** the model uses by itself (several at once in a single turn, if needed):
  - `get_weather(city)`: weather for a city (**fake** data, a constant answer),
  - `calculate(expression)`: a calculator built on the `ast` parser (`+ - * / ** %`, parentheses,
    unary minus), no `eval()`, so the model cannot run arbitrary Python code,
  - `save_note(note)`: appends a note to a text file.
- **`/podsumuj`** (summarize): a separate agent returns the conversation summary as a Pydantic
  object (topics and open issues) instead of free-form text.
- **`/cost`**: tokens, number of requests and tool calls, and the session cost (when the provider
  reports a price; OpenRouter does).
- **Safeguards**: a limit of 10 model requests per turn, readable messages instead of tracebacks on
  errors.
- **Observability**: every run visible as a trace in [Logfire](https://logfire.pydantic.dev)
  (prompts, tool calls, tokens, timings). Optional.

### Stack

Python 3.14, Pydantic AI, OpenRouter (Claude Haiku 4.5 by default), pydantic-settings, Logfire,
pytest, [uv](https://docs.astral.sh/uv/).

### Getting started

[uv](https://docs.astral.sh/uv/) is required (it also manages the Python version).

1. Install dependencies:
   ```bash
   uv sync
   ```
2. Create a `.env` file in the project root with your OpenRouter key (get one at
   [openrouter.ai/keys](https://openrouter.ai/keys); `.env` is in `.gitignore`):
   ```
   OPENROUTER_API_KEY=your-key
   ```
3. Run:
   ```bash
   uv run cli-ai-assistant
   ```

#### Logfire (optional)

Data is sent to Logfire **only when credentials are present**. Without them the assistant works
normally: it asks no questions and sends nothing. To turn tracing on:

```bash
uv run logfire auth
uv run logfire projects use PROJECT_NAME --org ORGANIZATION_NAME
```

The account needs an organization and a project (create them in the browser). The credentials are
stored in the `.logfire/` directory (in `.gitignore`); alternatively set the `LOGFIRE_TOKEN`
environment variable. To stop sending data, delete `.logfire/` or unset the token. Note that full
prompts and tool results are sent to Logfire, including the conversation and note contents.

### Configuration

Environment variables or entries in `.env`:

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | none (required) | OpenRouter API key; missing or empty fails validation at startup |
| `MODEL` | `anthropic/claude-haiku-4.5` | model name from the OpenRouter catalog |
| `NOTES_FILE` | `data/notatki.txt` | file that `save_note` appends notes to |
| `HISTORY_FILE` | `data/historia.json` | file with the conversation history |

The `data/` directory is in `.gitignore`.

### Chat commands

| Command | What it does |
|---|---|
| `/podsumuj` | summarizes the conversation: topics and open issues (does not change the history) |
| `/cost` | usage and cost of the current session |
| `/exit` | quits (Ctrl+C or end of input also quit without an error) |

Example: `what's the weather in Krakow and what is 17% of 3450?` triggers two tools in one turn.
The assistant answers in Polish.

### Architecture

```
src/cli_ai_assistant/
├── config.py    settings (key, model, file paths) via pydantic-settings
├── logic.py     tool logic without the framework: safe calculator, note writing
├── agent.py     instructions, dependencies (deps), three tools, summary agent
├── models.py    PodsumowanieRozmowy: the summary agent's result
├── history.py   saving and loading the history (JSON), building the conversation transcript
└── main.py      CLI loop, commands, limits, cost, Logfire
tests/           tests for every module
```

### Design decisions

- **Notes path via `deps`.** `AsystentDeps` carries the file path, so the `save_note` tool knows no
  global location and tests write to a temporary directory.
- **Tools from one turn run concurrently.** Two parallel writes to one file could corrupt each
  other (on Windows, appending through separate handles is not atomic), so note writing is guarded
  by a lock.
- **Two kinds of tool errors.** A bad argument from the model (e.g. an invalid expression) ends in
  `ModelRetry`, because the model can fix it. Errors the model cannot fix (division by zero, a disk
  write error) go back to it as plain text, so it apologizes to the user and the program keeps
  running.
- **History vs. tools.** A persistent history makes the model inclined to answer from memory
  instead of asking the tool again, so the instructions say to call tools anew on every request.
- **Summary from a transcript, not from the history.** The summary agent has no tools, so it gets
  only the text of questions and answers (no tool calls or results). Its result is not added to
  the conversation history.
- **Request limit per turn, not per session.** A turn with a tool takes at least two model requests
  (the tool request and the answer after its result), hence the limit of 10.
- **A corrupted history file does not stop the program.** If the file is empty, truncated, not
  JSON, not a list of messages or not valid UTF-8, the assistant moves it aside as
  `historia.json.uszkodzony-<date>` (nothing is deleted, so you can still recover data by hand),
  warns you and starts with an empty history.

### Tests

```bash
uv run pytest
```

The tests need no API key and no network. The model is replaced with `FunctionModel` (hand-written
scenarios) and `TestModel`, a dummy key is set before the imports, and real model calls are blocked
(`ALLOW_MODEL_REQUESTS = False`). They cover: the tool logic (including rejection of unsafe
expressions), tools inside the agent (retry, errors, several tools at once), saving and loading the
history, the CLI loop (restart with history, limit, `/cost`, `/podsumuj`), and the configuration.

### Known limitations

- The weather is fake (a constant answer): a demonstration of a tool, not an API integration.
- The calculator allows `**` with no limit on the exponent, so a very large power can keep the CPU
  busy for a long time.
- The whole history is sent to the model on every request, so the cost of later turns grows with
  the length of the conversation (no trimming and no cost limit for a whole session). `/podsumuj`
  sends the whole transcript.

---

## Polski

Konsolowy asystent AI napisany w [Pydantic AI](https://ai.pydantic.dev). Rozmawia w terminalu,
samodzielnie wybiera spośród trzech narzędzi, pamięta rozmowę między uruchomieniami, potrafi
podsumować ją jako ustrukturyzowany obiekt i zostawia pełny ślad każdego przebiegu w Logfire.

### Co potrafi

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

### Stack

Python 3.14, Pydantic AI, OpenRouter (domyślnie Claude Haiku 4.5), pydantic-settings, Logfire,
pytest, [uv](https://docs.astral.sh/uv/).

### Uruchomienie

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
3. Uruchom:
   ```bash
   uv run cli-ai-assistant
   ```

#### Logfire (opcjonalnie)

Dane trafiają do Logfire **tylko wtedy, gdy są dane logowania**. Bez nich asystent działa normalnie:
o nic nie pyta i niczego nie wysyła. Żeby włączyć śledzenie:

```bash
uv run logfire auth
uv run logfire projects use NAZWA_PROJEKTU --org NAZWA_ORGANIZACJI
```

Konto musi mieć organizację i projekt (załóż je w przeglądarce). Dane logowania trafiają do katalogu
`.logfire/` (jest w `.gitignore`); można też ustawić zmienną środowiskową `LOGFIRE_TOKEN`. Żeby
przestać wysyłać dane, usuń `.logfire/` albo odepnij token. Uwaga: do Logfire wysyłane są pełne
prompty i wyniki narzędzi, czyli także treść rozmowy i notatek.

### Konfiguracja

Zmienne środowiskowe lub wpisy w `.env`:

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `OPENROUTER_API_KEY` | brak (wymagana) | klucz API OpenRouter; brak lub pusty kończy się błędem walidacji przy starcie |
| `MODEL` | `anthropic/claude-haiku-4.5` | nazwa modelu w katalogu OpenRouter |
| `NOTES_FILE` | `data/notatki.txt` | plik, do którego `save_note` dopisuje notatki |
| `HISTORY_FILE` | `data/historia.json` | plik z historią rozmowy |

Katalog `data/` jest w `.gitignore`.

### Komendy w czacie

| Komenda | Działanie |
|---|---|
| `/podsumuj` | podsumowanie rozmowy: tematy i otwarte sprawy (nie zmienia historii) |
| `/cost` | zużycie i koszt bieżącej sesji |
| `/exit` | koniec programu (Ctrl+C lub koniec wejścia też kończą go bez błędu) |

Przykład: `jaka pogoda w Krakowie i ile to 17% z 3450?` wywoła dwa narzędzia w jednej turze.

### Architektura

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

### Decyzje projektowe

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
- **Uszkodzony plik historii nie zatrzymuje programu.** Jeśli plik jest pusty, urwany, nie jest
  JSON-em, nie jest listą wiadomości albo nie jest poprawnym UTF-8, asystent odkłada go jako
  `historia.json.uszkodzony-<data>` (nic nie jest kasowane, więc dane można jeszcze odzyskać
  ręcznie), uprzedza o tym i zaczyna z pustą historią.

### Testy

```bash
uv run pytest
```

Testy nie wymagają klucza API ani sieci. Model jest podmieniany na `FunctionModel` (scenariusze
pisane ręcznie) i `TestModel`, atrapa klucza jest ustawiana przed importem, a prawdziwe wywołania
modelu są zablokowane (`ALLOW_MODEL_REQUESTS = False`). Pokrywają: logikę narzędzi (w tym
odrzucanie niebezpiecznych wyrażeń), narzędzia w agencie (retry, błędy, kilka narzędzi naraz),
zapis i odczyt historii, pętlę CLI (restart z historią, limit, `/cost`, `/podsumuj`), konfigurację.

### Znane ograniczenia

- Pogoda jest fikcyjna (stała odpowiedź), to demonstracja narzędzia, a nie integracja z API.
- Kalkulator dopuszcza `**` bez limitu wielkości wykładnika, więc bardzo duża potęga może zająć
  procesor na długo.
- Cała historia jest wysyłana do modelu przy każdym żądaniu, więc koszt kolejnych tur rośnie
  z długością rozmowy (brak przycinania i limitu kosztu na całą sesję). `/podsumuj` wysyła całą
  transkrypcję.

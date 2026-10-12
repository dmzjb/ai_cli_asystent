"""Punkt wejścia CLI: pętla rozmowy, trwała historia, koszt sesji."""

import logfire
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import RunUsage, UsageLimits

from week_8_project.agent import AsystentDeps, agent, settings
from week_8_project.history import wczytaj_historie, zapisz_historie

# Tura z narzędziem to min. 2 requesty do modelu (prośba o narzędzie + odpowiedź), z retry więcej.
LIMIT_REQUESTOW_NA_TURE = 10


def pokaz_koszt(suma: RunUsage) -> None:
    print(
        f"tokeny: {suma.input_tokens} wejście / {suma.output_tokens} wyjście, "
        f"requesty: {suma.requests}, wywołania narzędzi: {suma.tool_calls}"
    )
    if suma.cost is None:
        print("koszt sesji: brak danych o cenie")
    else:
        print(f"koszt sesji do tej pory: ${suma.cost:.6f}")


def main() -> None:
    logfire.configure()
    logfire.instrument_pydantic_ai()

    deps = AsystentDeps(notes_file=settings.notes_file)
    historia = wczytaj_historie(settings.history_file)
    suma = RunUsage()
    limity = UsageLimits(request_limit=LIMIT_REQUESTOW_NA_TURE)

    print("Witaj w Asystencie CLI! Komendy: /cost, /exit")
    print(f"Model: {settings.model}. Wiadomości w historii: {len(historia)}")

    try:
        while True:
            prompt = input("\nTy: ").strip()
            if not prompt:
                continue
            if prompt == "/exit":
                break
            if prompt == "/cost":
                pokaz_koszt(suma)
                continue

            try:
                wynik = agent.run_sync(
                    prompt, deps=deps, message_history=historia, usage_limits=limity
                )
            except UsageLimitExceeded as e:
                # Przerwana tura nie trafia do historii (wynik nie istnieje).
                print(f"[Przekroczono limit w tej turze, spróbuj inaczej: {e}]")
                continue

            print(f"Bot: {wynik.output}")
            suma += wynik.usage
            historia += wynik.new_messages()
            zapisz_historie(settings.history_file, historia)
    except (EOFError, KeyboardInterrupt):
        print("\nDo zobaczenia!")


if __name__ == "__main__":
    main()

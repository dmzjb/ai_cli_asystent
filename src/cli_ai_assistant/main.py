"""Punkt wejścia CLI: pętla rozmowy, trwała historia, koszt sesji."""

import logfire
from pydantic_ai import ModelMessage
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.usage import RunUsage, UsageLimits

from cli_ai_assistant.agent import AsystentDeps, agent, settings, summary_agent
from cli_ai_assistant.history import (
    UszkodzonaHistoriaError,
    odloz_uszkodzona_historie,
    transkrypcja,
    wczytaj_historie,
    zapisz_historie,
)
from cli_ai_assistant.models import PodsumowanieRozmowy

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


def pokaz_podsumowanie(podsumowanie: PodsumowanieRozmowy) -> None:
    print("Podsumowanie rozmowy")
    print("Tematy:")
    for temat in podsumowanie.tematy or ["(brak)"]:
        print(f"  - {temat}")
    print("Otwarte sprawy:")
    for sprawa in podsumowanie.otwarte_sprawy or ["(brak)"]:
        print(f"  - {sprawa}")


def podsumuj(historia: list[ModelMessage]) -> RunUsage | None:
    """Wypisuje podsumowanie rozmowy. Zwraca zużycie lub None, gdy nie było czego podsumować
    albo model nie dał poprawnego wyniku. Nie zmienia historii: to osobny przebieg."""
    tekst = transkrypcja(historia)
    if not tekst:
        print("[Brak rozmowy do podsumowania]")
        return None
    try:
        wynik = summary_agent.run_sync(tekst)
    except UnexpectedModelBehavior as e:
        print(f"[Nie udało się przygotować podsumowania: {e}]")
        return None
    pokaz_podsumowanie(wynik.output)
    return wynik.usage


def main() -> None:
    # Wysyłka do Logfire tylko, gdy są dane logowania (.logfire/ lub LOGFIRE_TOKEN). Bez nich
    # program działa normalnie, bez pytań i bez wysyłania czegokolwiek.
    logfire.configure(send_to_logfire="if-token-present")
    logfire.instrument_pydantic_ai()

    deps = AsystentDeps(notes_file=settings.notes_file)
    try:
        historia = wczytaj_historie(settings.history_file)
    except UszkodzonaHistoriaError as e:
        kopia = odloz_uszkodzona_historie(settings.history_file)
        print(
            f"[Plik historii jest uszkodzony ({e}). Zachowano go jako {kopia}. Zaczynam od zera.]"
        )
        historia = []
    suma = RunUsage()
    limity = UsageLimits(request_limit=LIMIT_REQUESTOW_NA_TURE)

    print("Witaj w Asystencie CLI! Komendy: /cost, /exit, /podsumuj")
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
            if prompt == "/podsumuj":
                zuzycie = podsumuj(historia)
                if zuzycie is not None:
                    suma += zuzycie
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
    except EOFError, KeyboardInterrupt:
        print("\nDo zobaczenia!")


if __name__ == "__main__":
    main()

from pydantic import BaseModel, Field

class PodsumowanieRozmowy(BaseModel):
    tematy: list[str] = Field(
        description=(
            "Główne tematy rozmowy, każdy jako jedno krótkie hasło lub zdanie, "
            "np. 'pogoda w Krakowie' albo 'notatka o wizycie u dentysty'. Bez powtórzeń. "
            "Pusta lista, jeśli rozmowa nie miała merytorycznej treści."
        )
    )
    otwarte_sprawy: list[str] = Field(
        description=(
            "Rzeczy, o które użytkownik prosił lub które zostały zapowiedziane, a nie zostały "
            "doprowadzone do końca, np. pytanie bez odpowiedzi, błąd narzędzia albo prośba "
            "o doprecyzowanie. Pusta lista, jeśli wszystko zostało załatwione."
        )
    )

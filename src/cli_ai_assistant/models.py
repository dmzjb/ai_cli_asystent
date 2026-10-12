from pydantic import BaseModel, Field

class PodsumowanieRozmowy(BaseModel):
    tematy: list[str] = Field(description="...")
    otwarte_sprawy: list[str] = Field(description="...")
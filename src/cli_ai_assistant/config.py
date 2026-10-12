from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str = Field(
        default="", min_length=1
    )  # default="" tylko po to by type checker nie uznał pola za wymagane argumentem konstruktora. brak klucza i tak wywali się przy walidacji.
    model: str = "anthropic/claude-haiku-4.5"

    notes_file: Path = Path("data/notatki.txt")
    history_file: Path = Path("data/historia.json")

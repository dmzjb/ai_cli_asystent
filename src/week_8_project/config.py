from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str
    model: str = "anthropic/claude-haiku-4.5"

    notes_file: Path = Path("data/notatki.txt")
    history_file: Path = Path("data/historia.json")

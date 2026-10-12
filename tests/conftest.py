import os

# Atrapa klucza ustawiona PRZED importem cli_ai_assistant.agent: agent.py tworzy Settings() i model
# już przy imporcie, a zmienne środowiskowe mają pierwszeństwo przed .env. Dzięki temu testy
# nigdy nie używają prawdziwego klucza i przechodzą też bez pliku .env.
os.environ["OPENROUTER_API_KEY"] = "test-key-nieprawdziwy"

from pydantic_ai import models

# Każde przypadkowe wywołanie prawdziwego modelu w testach rzuci wyjątek zamiast kosztować.
models.ALLOW_MODEL_REQUESTS = False

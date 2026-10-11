"""ASGI-приложение. Запуск: ``uvicorn src.main:app``."""

from dotenv import load_dotenv

load_dotenv()

from src.api import create_app  # noqa: E402

app = create_app()

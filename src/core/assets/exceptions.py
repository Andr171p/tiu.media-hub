
class InvalidCustomMetaError(Exception):
    """Кастомные метаданные не соответствуют схеме коллекции."""


class InvalidMetaSchemaError(ValueError):
    """Некорректная схема кастомных метаданных."""

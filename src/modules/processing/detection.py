"""Определение фактического типа файла по содержимому (libmagic), а не по расширению или заголовку."""

_GENERIC_TYPES = frozenset({"application/octet-stream", "application/zip", "text/plain"})
_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
    "image/x-png": "image/png",
    "application/x-pdf": "application/pdf",
}
_ZIP_CONTAINERS = (
    "application/vnd.openxmlformats-officedocument.",
    "application/vnd.oasis.opendocument.",
)

SAMPLE_SIZE = 16 * 1024


def normalize_mime(mime_type: str) -> str:
    base = mime_type.split(";", maxsplit=1)[0].strip().lower()
    return _ALIASES.get(base, base)


def detect_mime(sample: bytes) -> str:
    # libmagic подключается лениво: API её не использует, а в образе воркера она установлена
    import magic

    return normalize_mime(magic.from_buffer(sample, mime=True))


def is_compatible(declared: str, detected: str) -> bool:
    """Заявленный тип не противоречит фактическому. libmagic иногда видит лишь контейнер (zip)."""

    declared, detected = normalize_mime(declared), normalize_mime(detected)

    if declared in {detected, "application/octet-stream"}:
        return True
    if declared.startswith("text/") and detected.startswith("text/"):
        return True
    return detected in {"application/zip", "application/octet-stream"} and declared.startswith(
        _ZIP_CONTAINERS
    )


def effective_mime(declared: str, detected: str) -> str:
    """
    Тип, по которому применяется политика коллекции: фактический, но уточнённый заявленным,
    если libmagic распознал только общий контейнер.
    """

    declared = normalize_mime(declared)
    if declared not in _GENERIC_TYPES and detected in _GENERIC_TYPES and is_compatible(declared, detected):
        return declared
    return detected


__all__ = ["SAMPLE_SIZE", "detect_mime", "effective_mime", "is_compatible", "normalize_mime"]

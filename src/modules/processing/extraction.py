"""Извлечение технических метаданных и изображения для производных.

Синхронный CPU-код: вызывается в потоке.
"""

from typing import IO, Any

import io
import logging
from dataclasses import dataclass
from datetime import datetime

from PIL import ExifTags, Image, ImageCms, UnidentifiedImageError

from src.modules.assets import (
    AssetKind,
    DocumentMeta,
    EmbeddedMetadata,
    ImageMeta,
    OtherMeta,
    VersionMeta,
    kind_of,
)

from .config import ProcessingConfig

logger = logging.getLogger(__name__)

_PDF_TEXT_PAGES = 30
_EXIF_DATETIME_FORMAT = "%Y:%m:%d %H:%M:%S"


class UnprocessableFileError(Exception):
    """Файл не может быть обработан: повтор не поможет, версия отмечается как неуспешная."""


@dataclass(frozen=True, slots=True)
class Extracted:
    meta: VersionMeta
    image: Image.Image | None = None
    """Изображение для миниатюры и превью: первый кадр или первая страница."""

    text: str | None = None
    """Текст для полнотекстового поиска."""


# =================================================================================================
# Встроенные метаданные изображений: EXIF и XMP
# =================================================================================================


def _clean(value: Any) -> str | None:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    if not isinstance(value, str):
        return None
    return value.replace("\x00", "").strip() or None


_XMP_CONTAINERS = ("Alt", "Seq", "Bag", "li")


def _xmp_strings(value: Any) -> list[str]:
    """Строки значения XMP: Pillow отдаёт RDF-контейнеры (Alt, Seq, Bag, li) как вложенные dict/list."""

    if isinstance(value, str):
        return [text] if (text := value.strip()) else []
    if isinstance(value, list):
        return [text for item in value for text in _xmp_strings(item)]
    if isinstance(value, dict):
        nested = [value.get("text"), *(value.get(name) for name in _XMP_CONTAINERS)]
        return [text for item in nested if item is not None for text in _xmp_strings(item)]
    return []


def _xmp_values(node: Any, key: str) -> list[str]:
    """Все значения поля XMP с именем ``key`` на любом уровне вложенности, без повторов."""

    if isinstance(node, dict):
        found = [
            text
            for name, child in node.items()
            for text in (_xmp_strings(child) if name == key else _xmp_values(child, key))
        ]
    elif isinstance(node, list):
        found = [text for item in node for text in _xmp_values(item, key)]
    else:
        found = []
    return list(dict.fromkeys(found))


def _first(*values: str | None) -> str | None:
    return next((value for value in values if value), None)


def _parse_exif_datetime(value: str | None) -> datetime | None:
    try:
        return datetime.strptime(value, _EXIF_DATETIME_FORMAT) if value else None
    except ValueError:
        return None


def _embedded_from_image(image: Image.Image) -> EmbeddedMetadata:
    exif = image.getexif()
    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)

    try:
        xmp = image.getxmp()
    except Exception:
        logger.warning("Failed to parse XMP metadata", exc_info=True)
        xmp = {}

    def xmp_first(key: str) -> str | None:
        return next(iter(_xmp_values(xmp, key)), None)

    make, model = _clean(exif.get(ExifTags.Base.Make)), _clean(exif.get(ExifTags.Base.Model))
    camera = " ".join(dict.fromkeys(part for part in (make, model) if part)) or None

    return EmbeddedMetadata(
        title=xmp_first("title"),
        description=_first(xmp_first("description"), _clean(exif.get(ExifTags.Base.ImageDescription))),
        creator=_first(
            _clean(exif.get(ExifTags.Base.Artist)), ", ".join(_xmp_values(xmp, "creator")) or None
        ),
        copyright=_first(_clean(exif.get(ExifTags.Base.Copyright)), xmp_first("rights")),
        usage_terms=xmp_first("UsageTerms"),
        web_statement=xmp_first("WebStatement"),
        keywords=_xmp_values(xmp, "subject")[:50],
        captured_at=_parse_exif_datetime(
            _first(
                _clean(exif_ifd.get(ExifTags.Base.DateTimeOriginal)),
                _clean(exif.get(ExifTags.Base.DateTime)),
            ),
        ),
        camera=camera,
        software=_clean(exif.get(ExifTags.Base.Software)),
        has_location=bool(exif.get_ifd(ExifTags.IFD.GPSInfo)),
    )


def _icc_description(image: Image.Image) -> str | None:
    if not (icc := image.info.get("icc_profile")):
        return None
    try:
        return ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(icc))).strip() or None
    except ImageCms.PyCMSError, OSError:
        return None


def _extract_image(file: IO[bytes], mime_type: str, config: ProcessingConfig) -> Extracted:
    Image.MAX_IMAGE_PIXELS = config.max_image_pixels

    try:
        image = Image.open(file)
    except UnidentifiedImageError:
        # Формат, который Pillow не декодирует (SVG, HEIC…): храним без превью
        return Extracted(meta=OtherMeta(mime_type=mime_type))
    except Image.DecompressionBombError as exc:
        raise UnprocessableFileError("Изображение слишком большое для обработки.") from exc

    with image:
        width, height = image.size
        meta = ImageMeta(
            mime_type=mime_type,
            format=image.format,
            width=width,
            height=height,
            mode=image.mode,
            has_alpha=image.mode in {"RGBA", "LA", "PA"} or "transparency" in image.info,
            dpi=tuple(float(value) for value in image.info["dpi"])[:2] if "dpi" in image.info else None,  # type: ignore[arg-type]
            icc_profile=_icc_description(image),
            frames=getattr(image, "n_frames", 1),
            embedded=_embedded_from_image(image),
        )

        # JPEG декодируется сразу в уменьшенном масштабе: в разы быстрее для больших фото
        image.draft(None, (config.preview_size, config.preview_size))
        try:
            image.load()
        except OSError as exc:
            raise UnprocessableFileError("Файл изображения повреждён.") from exc

        return Extracted(meta=meta, image=image.copy())


# =================================================================================================
# Документы
# =================================================================================================


def _pdf_date(value: str | None) -> datetime | None:
    # Формат PDF: D:YYYYMMDDHHmmSS…
    if not value:
        return None
    digits = value.removeprefix("D:")[:14]
    try:
        return datetime.strptime(digits.ljust(14, "0"), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def _extract_pdf(file: IO[bytes], config: ProcessingConfig) -> Extracted:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(file.read())
    except pdfium.PdfiumError as exc:
        if "password" in str(exc).lower():
            return Extracted(meta=DocumentMeta(mime_type="application/pdf", is_encrypted=True))
        raise UnprocessableFileError("PDF повреждён или не поддерживается.") from exc

    with pdf:
        info = pdf.get_metadata_dict(skip_empty=True)
        page_count = len(pdf)

        chunks: list[str] = []
        length = 0
        for index in range(min(page_count, _PDF_TEXT_PAGES)):
            if length >= config.text_excerpt_chars:
                break
            page = pdf[index]
            text = page.get_textpage().get_text_bounded().strip()
            chunks.append(text)
            length += len(text)
        text = "\n".join(chunk for chunk in chunks if chunk)[: config.text_excerpt_chars]

        image = None
        if page_count:
            page = pdf[0]
            scale = config.preview_size / max(page.get_size())
            image = page.render(scale=scale, may_draw_forms=True).to_pil()

    meta = DocumentMeta(
        mime_type="application/pdf",
        page_count=page_count,
        has_text_layer=bool(text),
        is_encrypted=False,
        embedded=EmbeddedMetadata(
            title=_clean(info.get("Title")),
            description=_clean(info.get("Subject")),
            creator=_clean(info.get("Author")),
            keywords=[word.strip() for word in (info.get("Keywords") or "").split(",") if word.strip()][:50],
            captured_at=_pdf_date(info.get("CreationDate")),
            software=_first(_clean(info.get("Creator")), _clean(info.get("Producer"))),
        ),
    )
    return Extracted(meta=meta, image=image, text=text or None)


def _extract_text(file: IO[bytes], mime_type: str, config: ProcessingConfig) -> Extracted:
    # Текст в UTF-8 или cp1251 (частый случай для русскоязычных CSV/TXT)
    raw = file.read(config.text_excerpt_chars * 4)
    for encoding in ("utf-8", "cp1251"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", "replace")

    text = text[: config.text_excerpt_chars].strip()
    return Extracted(meta=DocumentMeta(mime_type=mime_type, has_text_layer=bool(text)), text=text or None)


def extract(file: IO[bytes], mime_type: str, config: ProcessingConfig) -> Extracted:
    match kind_of(mime_type):
        case AssetKind.IMAGE:
            return _extract_image(file, mime_type, config)
        case AssetKind.DOCUMENT if mime_type == "application/pdf":
            return _extract_pdf(file, config)
        case AssetKind.DOCUMENT if mime_type.startswith("text/"):
            return _extract_text(file, mime_type, config)
        case AssetKind.DOCUMENT:
            return Extracted(meta=DocumentMeta(mime_type=mime_type))
        case _:
            return Extracted(meta=OtherMeta(mime_type=mime_type))


__all__ = ["Extracted", "UnprocessableFileError", "extract"]

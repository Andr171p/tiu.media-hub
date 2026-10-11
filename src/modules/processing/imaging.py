"""Производные изображения и водяной знак. Синхронный CPU-код: вызывается в потоке."""

import io
import logging
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from PIL import Image, ImageCms, ImageColor, ImageDraw, ImageFont, ImageOps

from src.modules.collections import ImageWatermark, TextWatermark
from src.modules.collections.settings import WatermarkPlacement

logger = logging.getLogger(__name__)

WEBP_CONTENT_TYPE = "image/webp"

_SRGB = ImageCms.createProfile("sRGB")
_MEASURE_FONT_SIZE = 100


@dataclass(frozen=True, slots=True)
class EncodedImage:
    data: bytes
    width: int
    height: int
    content_type: str = WEBP_CONTENT_TYPE


def _to_srgb(image: Image.Image) -> Image.Image:
    """Приводит цвета к sRGB по встроенному ICC-профилю: иначе CMYK и Adobe RGB в браузере «выцветают»."""

    has_alpha = image.mode in {"RGBA", "LA", "PA"} or "transparency" in image.info
    target_mode = "RGBA" if has_alpha else "RGB"

    if icc := image.info.get("icc_profile"):
        try:
            source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            if image.mode not in {"RGB", "RGBA", "CMYK"}:
                image = image.convert("RGBA" if has_alpha else "RGB")
            output_mode = target_mode if image.mode != "CMYK" else "RGB"
            return ImageCms.profileToProfile(image, source, _SRGB, outputMode=output_mode)
        except ImageCms.PyCMSError, OSError, ValueError:
            logger.warning("Failed to apply ICC profile, falling back to plain conversion", exc_info=True)

    return image.convert(target_mode)


def prepare(image: Image.Image) -> Image.Image:
    """Учитывает ориентацию EXIF и цветовой профиль: дальше работаем с «правильной» картинкой в sRGB."""

    return _to_srgb(ImageOps.exif_transpose(image))


def _resize(image: Image.Image, max_side: int) -> Image.Image:
    resized = image.copy()
    resized.thumbnail((max_side, max_side), Image.Resampling.LANCZOS, reducing_gap=3.0)
    return resized


def _encode_webp(image: Image.Image, quality: int) -> EncodedImage:
    buffer = io.BytesIO()
    # Метаданные не переносятся: в производных нет EXIF и GPS оригинала
    image.save(buffer, format="WEBP", quality=quality, method=4)
    return EncodedImage(data=buffer.getvalue(), width=image.width, height=image.height)


# =================================================================================================
# Водяной знак
# =================================================================================================


@cache
def _load_font_face(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        logger.warning("Watermark font %s not found, using Pillow default font", path)
        return None


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if (face := _load_font_face(path)) is not None:
        return ImageFont.truetype(io.BytesIO(face), size)
    return ImageFont.load_default(size=size)


def _clamp_box(center: float, size: int, limit: int) -> int:
    return int(min(max(center - size / 2, 0), max(limit - size, 0)))


def _position(
    image: Image.Image, mark_size: tuple[int, int], placement: WatermarkPlacement
) -> tuple[int, int]:
    width, height = mark_size
    return (
        _clamp_box(placement.x * image.width, width, image.width),
        _clamp_box(placement.y * image.height, height, image.height),
    )


def _text_layer(image: Image.Image, watermark: TextWatermark, font_path: Path) -> Image.Image:
    target_width = max(int(image.width * watermark.placement.scale), 1)

    # Подбираем кегль так, чтобы ширина текста равнялась заданной доле ширины кадра
    measured = ImageDraw.Draw(image).textlength(watermark.text, font=_font(font_path, _MEASURE_FONT_SIZE))
    size = max(int(_MEASURE_FONT_SIZE * target_width / max(measured, 1)), 8)
    font = _font(font_path, size)

    red, green, blue = ImageColor.getrgb(watermark.color)[:3]
    alpha = int(255 * watermark.placement.opacity)
    # Контрастная обводка: знак читается и на светлом, и на тёмном фоне
    stroke = (0, 0, 0) if (0.299 * red + 0.587 * green + 0.114 * blue) > 128 else (255, 255, 255)  # noqa: PLR2004

    stroke_width = max(size // 24, 1)
    left, top, right, bottom = font.getbbox(watermark.text, stroke_width=stroke_width)
    text_size = (right - left, bottom - top)
    x, y = _position(image, text_size, watermark.placement)

    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(
        (x - left, y - top),
        watermark.text,
        font=font,
        fill=(red, green, blue, alpha),
        stroke_width=stroke_width,
        stroke_fill=(*stroke, int(alpha * 0.6)),
    )
    return layer


def _image_layer(image: Image.Image, watermark: ImageWatermark, mark: Image.Image) -> Image.Image:
    mark = mark.convert("RGBA")
    width = max(int(image.width * watermark.placement.scale), 1)
    height = max(int(mark.height * width / mark.width), 1)
    mark = mark.resize((width, height), Image.Resampling.LANCZOS)

    alpha = mark.getchannel("A").point(lambda value: int(value * watermark.placement.opacity))
    mark.putalpha(alpha)

    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    layer.alpha_composite(mark, _position(image, mark.size, watermark.placement))
    return layer


def apply_watermark(
    image: Image.Image,
    watermark: ImageWatermark | TextWatermark,
    *,
    mark: Image.Image | None,
    font_path: Path,
) -> Image.Image:
    match watermark:
        case TextWatermark():
            layer = _text_layer(image, watermark, font_path)
        case ImageWatermark() if mark is not None:
            layer = _image_layer(image, watermark, mark)
        case _:
            logger.warning("Watermark image is unavailable, preview is rendered without watermark")
            return image

    result = Image.alpha_composite(image.convert("RGBA"), layer)
    return result if image.mode == "RGBA" else result.convert("RGB")


# =================================================================================================
# Производные
# =================================================================================================


def render_thumbnail(image: Image.Image, *, size: int, quality: int) -> EncodedImage:
    return _encode_webp(_resize(image, size), quality)


def render_preview(
    image: Image.Image,
    *,
    size: int,
    quality: int,
    watermark: ImageWatermark | TextWatermark | None,
    mark: Image.Image | None,
    font_path: Path,
) -> EncodedImage:
    preview = _resize(image, size)
    if watermark is not None:
        preview = apply_watermark(preview, watermark, mark=mark, font_path=font_path)
    return _encode_webp(preview, quality)


def open_image(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        return image.copy()


__all__ = [
    "EncodedImage",
    "apply_watermark",
    "open_image",
    "prepare",
    "render_preview",
    "render_thumbnail",
]

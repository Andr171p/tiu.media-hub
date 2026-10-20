import asyncio
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, UnidentifiedImageError
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.application.editing import EditRecipe, Filter, ImageEditor, TextLayerDTO
from src.application.processing.ports import UnsupportedMediaError


class EditorConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EDITOR_")

    font_regular: Path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font_bold: Path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


_ROTATIONS = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180, 270: Image.Transpose.ROTATE_90}
_FORMATS = {"jpeg": ("JPEG", "image/jpeg"), "png": ("PNG", "image/png"), "webp": ("WEBP", "image/webp")}


def _tint(image: Image.Image, color: tuple[int, int, int], strength: float) -> Image.Image:
    overlay = Image.new("RGB", image.size, color)
    return Image.blend(image, overlay, strength)


def _apply_filter(image: Image.Image, name: Filter) -> Image.Image:
    match name:
        case "grayscale":
            return ImageOps.grayscale(image).convert("RGB")
        case "sepia":
            return ImageOps.colorize(ImageOps.grayscale(image), "#2e1f0f", "#f5e6c8")
        case "warm":
            return _tint(image, (255, 160, 60), 0.12)
        case "cool":
            return _tint(image, (60, 140, 255), 0.12)
        case "vintage":
            faded = ImageEnhance.Contrast(ImageEnhance.Color(image).enhance(0.6)).enhance(0.85)
            return _tint(faded, (240, 200, 140), 0.15)

    return image


def _font(
    config: EditorConfig, layer: TextLayerDTO, height: int
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = max(8, int(layer.size * height))
    try:
        return ImageFont.truetype(str(config.font_bold if layer.bold else config.font_regular), size)
    except OSError:
        return ImageFont.load_default(size)


def _draw_text(image: Image.Image, layer: TextLayerDTO, config: EditorConfig) -> None:
    draw = ImageDraw.Draw(image)
    font = _font(config, layer, image.height)
    position = (layer.x * image.width, layer.y * image.height)

    if layer.shadow:
        offset = max(1, int(layer.size * image.height * 0.06))
        draw.text(
            (position[0] + offset, position[1] + offset), layer.text, font=font, fill="#000000A0", anchor="mm"
        )

    draw.text(position, layer.text, font=font, fill=layer.color, anchor="mm")


def _transform(image: Image.Image, recipe: EditRecipe) -> Image.Image:
    """Геометрия: поворот и отражение → кадрирование → размер."""

    if recipe.rotate:
        image = image.transpose(_ROTATIONS[recipe.rotate])
    if recipe.flip_horizontal:
        image = ImageOps.mirror(image)
    if recipe.flip_vertical:
        image = ImageOps.flip(image)

    if crop := recipe.crop:
        left, top = round(crop.x * image.width), round(crop.y * image.height)
        right = min(image.width, round((crop.x + crop.width) * image.width))
        bottom = min(image.height, round((crop.y + crop.height) * image.height))
        image = image.crop((left, top, max(right, left + 1), max(bottom, top + 1)))

    if (resize := recipe.resize) and (resize.width or resize.height):
        image.thumbnail(
            (resize.width or image.width, resize.height or image.height), Image.Resampling.LANCZOS
        )

    return image


def render(source: Path, recipe: EditRecipe, output: Path, config: EditorConfig) -> str:
    """Применяет рецепт по порядку: геометрия → коррекция → фильтр → текст."""

    try:
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise UnsupportedMediaError(f"Cannot read image: {exc}") from exc

    image = _transform(image, recipe)

    adjustments = recipe.adjustments
    for enhancer, value in (
        (ImageEnhance.Brightness, adjustments.brightness),
        (ImageEnhance.Contrast, adjustments.contrast),
        (ImageEnhance.Color, adjustments.saturation),
    ):
        if value:
            image = enhancer(image).enhance(1 + value)

    image = _apply_filter(image, recipe.filter)

    if recipe.texts:
        image = image.convert("RGBA")
        for layer in recipe.texts:
            _draw_text(image, layer, config)
        image = image.convert("RGB")

    image_format, content_type = _FORMATS[recipe.format]
    options = {"quality": recipe.quality} if recipe.format != "png" else {"optimize": True}
    image.save(output, image_format, **options)
    return content_type


class PillowImageEditor(ImageEditor):
    def __init__(self, config: EditorConfig) -> None:
        self._config = config

    async def render(self, source: Path, recipe: EditRecipe, output: Path) -> str:
        return await asyncio.to_thread(render, source, recipe, output, self._config)


__all__ = ["EditorConfig", "PillowImageEditor", "render"]

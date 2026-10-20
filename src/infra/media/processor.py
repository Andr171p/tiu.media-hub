"""Технические метаданные и производные: изображения — Pillow, видео и аудио — ffmpeg, PDF — pdfium."""

from typing import Any

import asyncio
import json
import logging
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pypdfium2
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener
from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.application.processing.ports import (
    Frame,
    MediaProcessor,
    ProcessedMedia,
    RenditionFile,
    UnsupportedMediaError,
)
from src.domain.assets import AssetKind, RenditionKind, VersionMeta

logger = logging.getLogger(__name__)

register_heif_opener()
Image.MAX_IMAGE_PIXELS = 500_000_000

_EXIF_DATETIME_ORIGINAL = 36867
_EXIF_MAKE, _EXIF_MODEL = 271, 272
_EXIF_IFD = 0x8769


class MediaConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEDIA_")

    thumbnail_size: PositiveInt = 480
    preview_size: PositiveInt = 2048
    proxy_height: PositiveInt = 720
    video_encoder: str = "libx264"
    """``h264_nvenc`` для GPU, если ffmpeg собран с NVENC."""

    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"


async def _run(*args: str) -> bytes:
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        message = stderr.decode(errors="replace").strip().splitlines()
        raise UnsupportedMediaError(message[-1] if message else f"{args[0]} failed")

    return stdout


def _save_webp(
    image: Image.Image, path: Path, kind: RenditionKind, *, size: int, quality: int
) -> RenditionFile:
    copy = image.copy()
    copy.thumbnail((size, size), Image.Resampling.LANCZOS)
    copy.save(path, "WEBP", quality=quality, method=4)
    return RenditionFile(
        kind=kind, path=path, content_type="image/webp", width=copy.width, height=copy.height
    )


def _image_renditions(image: Image.Image, workdir: Path, config: MediaConfig) -> list[RenditionFile]:
    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")

    return [
        _save_webp(
            image, workdir / "preview.webp", RenditionKind.PREVIEW, size=config.preview_size, quality=85
        ),
        _save_webp(
            image, workdir / "thumbnail.webp", RenditionKind.THUMBNAIL, size=config.thumbnail_size, quality=80
        ),
    ]


def _exif_meta(image: Image.Image) -> tuple[datetime | None, str | None]:
    exif = image.getexif()
    camera = " ".join(str(exif.get(tag, "")).strip("\x00 ") for tag in (_EXIF_MAKE, _EXIF_MODEL)).strip()
    raw = exif.get_ifd(_EXIF_IFD).get(_EXIF_DATETIME_ORIGINAL)

    try:
        captured_at = datetime.strptime(str(raw).strip("\x00 "), "%Y:%m:%d %H:%M:%S") if raw else None
    except ValueError:
        captured_at = None

    return captured_at, camera or None


def _process_image(source: Path, workdir: Path, config: MediaConfig) -> ProcessedMedia:
    try:
        with Image.open(source) as opened:
            captured_at, camera = _exif_meta(opened)
            width, height = opened.size
            frames = getattr(opened, "n_frames", 1)
            opened.draft("RGB", (config.preview_size, config.preview_size))
            image = ImageOps.exif_transpose(opened)
            image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise UnsupportedMediaError(f"Cannot read image: {exc}") from exc

    if image.width < image.height and width > height:  # поворот из EXIF
        width, height = height, width

    meta = VersionMeta(width=width, height=height, captured_at=captured_at, camera=camera)
    if frames > 1:
        logger.debug("Animated or multi-page image: using the first frame")

    return ProcessedMedia(meta=meta, renditions=_image_renditions(image, workdir, config))


def _process_pdf(source: Path, workdir: Path, config: MediaConfig) -> ProcessedMedia:
    try:
        document = pypdfium2.PdfDocument(source)
    except pypdfium2.PdfiumError as exc:
        raise UnsupportedMediaError(f"Cannot read PDF: {exc}") from exc

    try:
        page_count = len(document)
        if not page_count:
            return ProcessedMedia(meta=VersionMeta(page_count=0), renditions=[])

        page = document[0]
        scale = config.preview_size / max(page.get_size())
        image = page.render(scale=scale).to_pil()
    finally:
        document.close()

    return ProcessedMedia(
        meta=VersionMeta(width=image.width, height=image.height, page_count=page_count),
        renditions=_image_renditions(image, workdir, config),
    )


def _fps(value: str | None) -> float | None:
    try:
        return round(float(Fraction(value)), 3) if value and value != "0/0" else None
    except ValueError, ZeroDivisionError:
        return None


class FfmpegMediaProcessor(MediaProcessor):
    def __init__(self, config: MediaConfig) -> None:
        self._config = config

    async def _probe(self, source: Path) -> dict[str, Any]:
        output = await _run(
            self._config.ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(source),
        )
        return json.loads(output)

    async def process(self, source: Path, kind: AssetKind, workdir: Path) -> ProcessedMedia:
        match kind:
            case AssetKind.IMAGE:
                return await asyncio.to_thread(_process_image, source, workdir, self._config)
            case AssetKind.DOCUMENT:
                return await asyncio.to_thread(_process_pdf, source, workdir, self._config)
            case AssetKind.VIDEO:
                return await self._process_video(source, workdir)
            case AssetKind.AUDIO:
                return await self._process_audio(source, workdir)

        return ProcessedMedia(meta=VersionMeta(), renditions=[])

    async def _process_video(self, source: Path, workdir: Path) -> ProcessedMedia:
        probe = await self._probe(source)
        streams = probe.get("streams", [])
        video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)

        if video is None:
            raise UnsupportedMediaError("No video stream found.")

        duration = float(probe.get("format", {}).get("duration") or video.get("duration") or 0)
        poster = workdir / "poster.jpg"
        poster_at = f"{min(duration * 0.1, 5):.2f}"
        await _run(
            self._config.ffmpeg, "-y", "-v", "error", "-ss", poster_at, "-i", str(source),
            "-frames:v", "1", "-q:v", "2", str(poster),
        )  # fmt: skip

        proxy = workdir / "proxy.mp4"
        height = self._config.proxy_height
        await _run(
            self._config.ffmpeg, "-y", "-v", "error", "-i", str(source),
            "-map", "0:v:0", "-map", "0:a:0?",
            "-vf", f"scale=-2:'min({height},ih)'", "-c:v", self._config.video_encoder,
            "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(proxy),
        )  # fmt: skip

        with Image.open(poster) as frame:
            image_renditions = await asyncio.to_thread(
                _image_renditions, frame.convert("RGB"), workdir, self._config
            )

        proxy_meta = await self._probe(proxy)
        proxy_video = next(stream for stream in proxy_meta["streams"] if stream.get("codec_type") == "video")
        width, height_ = int(video.get("width", 0)), int(video.get("height", 0))
        rotation = abs(int(next((data.get("rotation", 0) for data in video.get("side_data_list", [])), 0)))
        if rotation in {90, 270}:
            width, height_ = height_, width

        return ProcessedMedia(
            meta=VersionMeta(
                width=width or None,
                height=height_ or None,
                duration=round(duration, 3) or None,
                frame_rate=_fps(video.get("avg_frame_rate")),
                video_codec=video.get("codec_name"),
                audio_codec=audio.get("codec_name") if audio else None,
            ),
            renditions=[
                *image_renditions,
                RenditionFile(
                    kind=RenditionKind.VIDEO,
                    path=proxy,
                    content_type="video/mp4",
                    width=proxy_video.get("width"),
                    height=proxy_video.get("height"),
                ),
            ],
        )

    async def _process_audio(self, source: Path, workdir: Path) -> ProcessedMedia:
        probe = await self._probe(source)
        audio = next(
            (stream for stream in probe.get("streams", []) if stream.get("codec_type") == "audio"), None
        )
        if audio is None:
            raise UnsupportedMediaError("No audio stream found.")

        proxy = workdir / "proxy.m4a"
        await _run(
            self._config.ffmpeg, "-y", "-v", "error", "-i", str(source), "-vn",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(proxy),
        )  # fmt: skip

        duration = float(probe.get("format", {}).get("duration") or 0)
        return ProcessedMedia(
            meta=VersionMeta(duration=round(duration, 3) or None, audio_codec=audio.get("codec_name")),
            renditions=[RenditionFile(kind=RenditionKind.AUDIO, path=proxy, content_type="audio/mp4")],
        )

    async def sample_frames(self, video: Path, *, max_frames: int) -> list[Frame]:
        probe = await self._probe(video)
        duration = float(probe.get("format", {}).get("duration") or 0)
        count = max(1, min(max_frames, int(duration // 2)))

        frames = []
        for index in range(count):
            timecode = round((index + 0.5) * duration / count, 2)
            image = await _run(
                self._config.ffmpeg, "-v", "error", "-ss", f"{timecode:.2f}", "-i", str(video),
                "-frames:v", "1", "-q:v", "3", "-f", "image2pipe", "-vcodec", "mjpeg", "-",
            )  # fmt: skip
            if image:
                frames.append(Frame(image=image, timecode=timecode))

        return frames


__all__ = ["FfmpegMediaProcessor", "MediaConfig"]

from pathlib import Path

import aiohttp
from pydantic import BaseModel, Field, HttpUrl, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.application.processing.ports import Transcriber, Transcript, TranscriptSegment


class WhisperConfig(BaseSettings):
    """Whisper ASR Web Service (faster-whisper)."""

    model_config = SettingsConfigDict(env_prefix="WHISPER_")

    url: HttpUrl = HttpUrl("http://localhost:9010")
    language: str | None = Field(default="ru", description="None — автоопределение")
    timeout: PositiveInt = Field(default=3600, description="Расшифровка длинного видео занимает минуты")


class _Segment(BaseModel):
    start: float
    end: float
    text: str


class _Result(BaseModel):
    language: str | None = None
    segments: list[_Segment] = Field(default_factory=list)


class WhisperTranscriber(Transcriber):
    def __init__(self, config: WhisperConfig) -> None:
        self._config = config

    async def transcribe(self, media: Path) -> Transcript:
        params = {"task": "transcribe", "output": "json", "encode": "true", "vad_filter": "true"}
        if self._config.language:
            params["language"] = self._config.language

        timeout = aiohttp.ClientTimeout(total=self._config.timeout)
        async with aiohttp.ClientSession(base_url=str(self._config.url), timeout=timeout) as session:
            with media.open("rb") as file:
                form = aiohttp.FormData()
                form.add_field("audio_file", file, filename=media.name)

                async with session.post("asr", params=params, data=form) as response:
                    response.raise_for_status()
                    result = _Result.model_validate_json(await response.read())

        return Transcript(
            language=result.language,
            segments=[
                TranscriptSegment(start=item.start, end=item.end, text=item.text.strip())
                for item in result.segments
                if item.text.strip()
            ],
        )


__all__ = ["WhisperConfig", "WhisperTranscriber"]

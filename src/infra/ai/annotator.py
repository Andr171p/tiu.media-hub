import base64
import json
import logging
from collections.abc import Sequence

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionContentPartParam
from pydantic import BaseModel, Field, HttpUrl, PositiveInt, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.application.processing.ports import Annotation, Frame, ImageAnnotator
from src.domain.assets import AssetKind

logger = logging.getLogger(__name__)


class VisionConfig(BaseSettings):
    """
    VLM через OpenAI-совместимый API: в разработке — дешёвая модель AITunnel,
    на сервере — локальная модель Ollama (``http://ollama:11434/v1``).
    """

    model_config = SettingsConfigDict(env_prefix="VISION_")

    base_url: HttpUrl = HttpUrl("https://api.aitunnel.ru/v1")
    api_key: SecretStr = SecretStr("")
    model: str = "gemini-2.5-flash-lite"
    max_tags: PositiveInt = 15
    timeout: PositiveInt = 120


_PROMPT = """Ты помогаешь каталогизировать медиатеку университета.
Посмотри на {subject} и ответь строго JSON-объектом без пояснений:
{{"caption": "одно-два предложения: что изображено, кто, что делает, где",
  "tags": ["до {max_tags} ключевых слов: объекты, люди, действия, эмоции, место, событие"]}}
Пиши на русском. Теги — существительные или короткие фразы в нижнем регистре, без повторов.
Не придумывай имена людей и надписи, которых не видно."""

_SUBJECTS = {AssetKind.VIDEO: "кадры одного видео (в хронологическом порядке)"}


class _Answer(BaseModel):
    caption: str = Field(max_length=1000)
    tags: list[str] = Field(default_factory=list)


def create_openai_client(config: VisionConfig) -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=str(config.base_url),
        api_key=config.api_key.get_secret_value() or "not-needed",
        timeout=config.timeout,
        max_retries=2,
    )


def _image_part(image: bytes) -> ChatCompletionContentPartParam:
    mime = "image/webp" if image[8:12] == b"WEBP" else "image/jpeg"
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{base64.b64encode(image).decode()}"},
    }


def _parse(content: str) -> _Answer:
    start, end = content.find("{"), content.rfind("}")
    return _Answer.model_validate(json.loads(content[start : end + 1]))


class OpenAIImageAnnotator(ImageAnnotator):
    def __init__(self, client: AsyncOpenAI, config: VisionConfig) -> None:
        self._client = client
        self._config = config

    async def annotate(self, frames: Sequence[Frame], *, kind: AssetKind) -> Annotation:
        prompt = _PROMPT.format(subject=_SUBJECTS.get(kind, "изображение"), max_tags=self._config.max_tags)
        content: list[ChatCompletionContentPartParam] = [
            {"type": "text", "text": prompt},
            *(_image_part(frame.image) for frame in frames),
        ]
        response = await self._client.chat.completions.create(
            model=self._config.model,
            messages=[{"role": "user", "content": content}],
            temperature=0.2,
        )
        text = response.choices[0].message.content or ""

        try:
            answer = _parse(text)
        except (ValueError, ValidationError) as exc:
            raise ValueError(f"Vision model returned an unexpected answer: {text[:200]!r}") from exc

        return Annotation(caption=answer.caption.strip(), tags=answer.tags[: self._config.max_tags])


__all__ = ["OpenAIImageAnnotator", "VisionConfig", "create_openai_client"]

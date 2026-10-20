from typing import Literal

import base64
from collections.abc import Sequence

import aiohttp
from pydantic import BaseModel, HttpUrl, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.application.search.ports import ClipEmbedder


class InfinityConfig(BaseSettings):
    """
    CLIP в Infinity: изображения кодирует CLIP ViT-B/32, текст — мультиязычный энкодер,
    дистиллированный в то же пространство (понимает русский).
    """

    model_config = SettingsConfigDict(env_prefix="INFINITY_")

    url: HttpUrl = HttpUrl("http://localhost:7997")
    image_model: str = "openai/clip-vit-base-patch32"
    text_model: str = "sentence-transformers/clip-ViT-B-32-multilingual-v1"
    batch_size: PositiveInt = 16
    timeout: PositiveInt = 120
    # Пороги зависят от модели: для CLIP ViT-B/32 релевантный текст даёт ~0.25, шум — до ~0.21
    text_match_score: float = 0.21
    image_match_score: float = 0.75


class _Item(BaseModel):
    index: int
    embedding: list[float]


class _Response(BaseModel):
    data: list[_Item]


def _data_uri(image: bytes) -> str:
    mime = "image/webp" if image[8:12] == b"WEBP" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(image).decode()}"


class InfinityClipEmbedder(ClipEmbedder):
    """OpenAI-совместимый ``POST /embeddings`` Infinity с полем ``modality``."""

    def __init__(self, config: InfinityConfig) -> None:
        self._config = config
        self._session: aiohttp.ClientSession | None = None
        self.text_match_score = config.text_match_score
        self.image_match_score = config.image_match_score

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                base_url=str(self._config.url),
                timeout=aiohttp.ClientTimeout(total=self._config.timeout),
            )
        return self._session

    async def _embed(self, inputs: Sequence[str], modality: Literal["text", "image"]) -> list[list[float]]:
        model = self._config.text_model if modality == "text" else self._config.image_model
        vectors: list[list[float]] = []

        for start in range(0, len(inputs), self._config.batch_size):
            payload = {
                "model": model,
                "input": list(inputs[start : start + self._config.batch_size]),
                "modality": modality,
            }
            async with self._get_session().post("embeddings", json=payload) as response:
                response.raise_for_status()
                result = _Response.model_validate(await response.json())

            vectors.extend(item.embedding for item in sorted(result.data, key=lambda item: item.index))

        return vectors

    async def embed_images(self, images: Sequence[bytes]) -> list[list[float]]:
        return await self._embed([_data_uri(image) for image in images], "image")

    async def embed_text(self, text: str) -> list[float]:
        [vector] = await self._embed([text], "text")
        return vector

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()


__all__ = ["InfinityClipEmbedder", "InfinityConfig"]

from typing import Literal

import base64
from collections.abc import Sequence
from dataclasses import dataclass

import aiohttp
from pydantic import BaseModel

from .config import InfinityConfig

type Vector = list[float]


class EmbeddingUnavailableError(Exception):
    """Сервер эмбеддингов недоступен или вернул некорректный ответ."""


@dataclass(frozen=True, slots=True)
class ImageInput:
    content: bytes
    content_type: str

    def to_data_uri(self) -> str:
        return f"data:{self.content_type};base64,{base64.b64encode(self.content).decode()}"


class _EmbeddingItem(BaseModel):
    index: int
    embedding: Vector


class _EmbeddingResponse(BaseModel):
    data: list[_EmbeddingItem]


class InfinityClient:
    """Клиент OpenAI-совместимого API Infinity (``POST /embeddings`` с ``modality``)."""

    def __init__(self, config: InfinityConfig) -> None:
        self._config = config
        self._session: aiohttp.ClientSession | None = None

    @property
    def dimensions(self) -> int:
        return self._config.dimensions

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                base_url=str(self._config.url),
                timeout=aiohttp.ClientTimeout(total=self._config.timeout),
            )
        return self._session

    async def _embed(self, inputs: Sequence[str], modality: Literal["text", "image"]) -> list[Vector]:
        vectors: list[Vector] = []
        session = self._get_session()

        for start in range(0, len(inputs), self._config.batch_size):
            batch = list(inputs[start : start + self._config.batch_size])
            payload = {"model": self._config.model, "input": batch, "modality": modality}

            try:
                async with session.post("embeddings", json=payload) as response:
                    response.raise_for_status()
                    result = _EmbeddingResponse.model_validate(await response.json())
            except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
                raise EmbeddingUnavailableError(f"Infinity request failed: {exc}") from exc

            vectors.extend(item.embedding for item in sorted(result.data, key=lambda item: item.index))

        return vectors

    async def embed_texts(self, texts: Sequence[str]) -> list[Vector]:
        return await self._embed(texts, "text")

    async def embed_text(self, text: str) -> Vector:
        [vector] = await self.embed_texts([text])
        return vector

    async def embed_images(self, images: Sequence[ImageInput]) -> list[Vector]:
        return await self._embed([image.to_data_uri() for image in images], "image")

    async def embed_image(self, image: ImageInput) -> Vector:
        [vector] = await self.embed_images([image])
        return vector

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None


__all__ = ["EmbeddingUnavailableError", "ImageInput", "InfinityClient", "Vector"]

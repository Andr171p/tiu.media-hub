import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from ddf.domain.exceptions import InvalidStateError, InvariantViolationError
from ddf.domain.models import AggregateRoot, Entity

from src.domain.collections import MetadataValue

from .events import AssetCurrentVersionChanged, AssetVersionAdded, AssetVersionProcessed
from .license import License


class AssetKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    OTHER = "other"

    @staticmethod
    def of(content_type: str) -> AssetKind:
        major, _, minor = content_type.lower().partition("/")

        if major in {"image", "video", "audio"}:
            return AssetKind(major)

        if minor == "pdf":
            return AssetKind.DOCUMENT

        return AssetKind.OTHER


@dataclass(frozen=True, kw_only=True)
class StoredFile:
    """Файл в объектном хранилище."""

    key: str
    name: str
    """Исходное имя файла."""

    content_type: str
    size: int


class RenditionKind(StrEnum):
    THUMBNAIL = "thumbnail"
    """Миниатюра для сеток (~480px)."""

    PREVIEW = "preview"
    """Крупное превью (~2048px): кадр-постер для видео, первая страница для документа."""

    VIDEO = "video"
    """Прокси-видео 720p H.264 для плеера."""

    AUDIO = "audio"
    """Прокси-аудио AAC для плеера."""


@dataclass(frozen=True, kw_only=True)
class Rendition:
    """Производная версии, раздаётся через CDN."""

    kind: RenditionKind
    file: StoredFile
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True, kw_only=True)
class VersionMeta:
    """Технические метаданные, извлечённые из файла при обработке."""

    width: int | None = None
    height: int | None = None
    duration: float | None = None
    """Секунды (видео, аудио)."""

    frame_rate: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    page_count: int | None = None
    captured_at: datetime | None = None
    camera: str | None = None


@dataclass(kw_only=True)
class AssetVersion(Entity):
    """Неизменяемый файл актива. Обработка только дописывает к нему метаданные и производные."""

    asset_id: UUID
    number: int
    file: StoredFile
    created_by: UUID
    source_version_id: UUID | None = None
    """Версия, из которой получен файл (редактор)."""

    note: str | None = None

    sha256: str | None = None
    meta: VersionMeta | None = None
    renditions: tuple[Rendition, ...] = ()
    processed_at: datetime | None = None
    processing_error: str | None = None

    @property
    def kind(self) -> AssetKind:
        return AssetKind.of(self.file.content_type)

    def rendition(self, kind: RenditionKind) -> Rendition | None:
        return next((rendition for rendition in self.renditions if rendition.kind is kind), None)

    def complete_processing(
        self, *, sha256: str, meta: VersionMeta, renditions: tuple[Rendition, ...]
    ) -> None:
        self.sha256 = sha256
        self.meta = meta
        self.renditions = renditions
        self.processing_error = None
        self.processed_at = self.updated_at = datetime.now(UTC)

        self.register_event(AssetVersionProcessed(asset_id=self.asset_id, version_id=self.id))

    def restart_processing(self) -> None:
        """Повторная обработка (например, после обновления обработчика)."""

        self.processed_at = self.processing_error = None
        self.updated_at = datetime.now(UTC)
        self.register_event(AssetVersionAdded(asset_id=self.asset_id, version_id=self.id))

    def fail_processing(self, error: str) -> None:
        """Файл не удалось разобрать: версия остаётся доступной для скачивания, но без превью."""

        self.processing_error = error
        self.processed_at = self.updated_at = datetime.now(UTC)


@dataclass(kw_only=True)
class Asset(AggregateRoot):
    """Единица контента: описание, теги, лицензия и история версий файла."""

    collection_id: UUID
    title: str
    kind: AssetKind
    created_by: UUID

    description: str | None = None
    caption: str | None = None
    """Описание изображения, сгенерированное ИИ: используется в полнотекстовом поиске."""

    tags: tuple[str, ...] = ()
    metadata: dict[str, MetadataValue] = field(default_factory=dict)
    license: License | None = None

    current_version_id: UUID
    version_count: int = 1

    def accepts(self, content_type: str) -> bool:
        """Новая версия должна быть того же вида: фото заменяется фото, видео — видео."""

        return AssetKind.of(content_type) is self.kind

    def add_version(
        self,
        file: StoredFile,
        *,
        created_by: UUID,
        source_version_id: UUID | None = None,
        note: str | None = None,
        version_id: UUID | None = None,
    ) -> AssetVersion:
        """Новая версия сразу становится текущей."""

        if self.is_deleted:
            raise InvalidStateError("Trashed asset cannot get new versions.")

        if not self.accepts(file.content_type):
            raise InvariantViolationError(f"New version must be {self.kind} like the asset.")

        self.version_count += 1
        version = AssetVersion(
            id=version_id or uuid.uuid7(),
            asset_id=self.id,
            number=self.version_count,
            file=file,
            created_by=created_by,
            source_version_id=source_version_id,
            note=note,
        )
        self.current_version_id = version.id
        self.updated_at = datetime.now(UTC)

        self.register_event(AssetVersionAdded(asset_id=self.id, version_id=version.id))
        return version

    def make_current(self, version: AssetVersion) -> None:
        if version.asset_id != self.id:
            raise InvariantViolationError(f"Version {version.id} does not belong to asset {self.id}.")

        if version.id == self.current_version_id:
            return

        self.current_version_id = version.id
        self.updated_at = datetime.now(UTC)

        self.register_event(AssetCurrentVersionChanged(asset_id=self.id, version_id=version.id))


@dataclass(kw_only=True)
class Upload(Entity):
    """Загрузка файла напрямую в хранилище: из неё создаётся актив или новая версия актива."""

    collection_id: UUID
    created_by: UUID
    file: StoredFile
    asset_id: UUID | None = None
    """Актив, к которому загружается новая версия."""

    multipart_id: str | None = None
    expires_at: datetime

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

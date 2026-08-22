import asyncio
from uuid import UUID

from temporalio.client import Client

from .config import TemporalConfig
from .dtos import AssetProcessingContext


class TemporalClient:
    def __init__(self, config: TemporalConfig) -> None:
        self._config = config
        self._client: Client | None = None
        self._lock = asyncio.Lock()

    async def _get_client(self) -> Client:
        """Потокобезопасно возвращает или лениво инициализирует gRPC-клиент Temporal."""

        if self._client is not None:
            return self._client

        async with self._lock:
            if self._client is None:
                self._client = await Client.connect(
                    target_host=self._config.address, namespace=self._config.namespace,
                )

            return self._client

    async def start_asset_processing(
            self, upload_id: UUID, context: AssetProcessingContext,
    ) -> None:
        """Запускает workflow для обработки медиа актива."""

        client = await self._get_client()

        await client.start_workflow(
            "AssetProcessingWorkflow",
            context,
            id=str(upload_id),
            task_queue=self._config.task_queue,
        )

    async def complete_asset_upload(self, upload_id: UUID) -> None:
        """Отправляет сигнал workflow о том, что загрузка файла в S3 успешно завершена."""

        client = await self._get_client()

        handle = client.get_workflow_handle(str(upload_id))

        # Отправка signal в работающий workflow.

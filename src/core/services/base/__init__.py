"""
Инфраструктура HTTP-клиентов для межсервисного взаимодействия.

Модуль предоставляет:class:`SrvBaseClient` — лёгкий базовый класс для
HTTP-клиентов, которые используют OAuth 2.0 Client Credentials Flow
для аутентификации.

Базовый клиент отвечает за общую транспортную и аутентификационную
инфраструктуру:

- создание и переиспользование `aiohttp.ClientSession`;
- управление пулом HTTP-соединений и таймаутами;
- получение OAuth access token;
- кеширование access token в памяти;
- заблаговременное обновление токена до истечения его срока действия;
- синхронизацию конкурентного обновления токена.

`SrvBaseClient` намеренно не реализует универсальный слой для выполнения
HTTP-запросов. Конкретные клиенты должны явно описывать операции своего
сервиса, включая URL, HTTP-методы, тело запроса, ожидаемые HTTP-статусы,
валидацию ответа и правила повторного выполнения запросов.

Пример:

```python

class CollectionsClient(SrvBaseClient):
    async def get_collection(self, collection_id: UUID) -> Collection:
        async with self._get_token_session() as session:
            async with session.get(
                f"{self.config.base_url}/collections/{collection_id}",
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return Collection.model_validate(data)
```

Клиент предполагается долгоживущим и должен переиспользоваться на протяжении
жизненного цикла приложения или worker-процесса.

При завершении работы приложения необходимо вызвать
`SrvBaseClient.close`, чтобы корректно закрыть HTTP-сессию и освободить
пул соединений.
"""

from .client import SrvBaseClient
from .config import SrvBaseConfig

__all__ = ["SrvBaseClient", "SrvBaseConfig"]

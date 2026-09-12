# Локальный Keycloak для DAM

Архитектура и ограничения описаны в [authentication_and_authorization.md](../Архитектура/authentication_and_authorization.md).

## Запуск

Заполнить .env по .env.example, затем:

```powershell
docker compose up -d keycloak-db keycloak
uv run uvicorn main:app --reload --env-file .env
```

Keycloak: http://localhost:8081, API OpenAPI: http://localhost:8000/docs.
Для backend на хосте JWKS_URL использует localhost:8081.
Из Docker использовать http://keycloak:8080 для JWKS и token endpoint;
issuer остаётся публичным http://localhost:8081/realms/tiu-media-hub.

Realm импортируется из keycloak/realm/tiu-media-hub-realm.json при первом старте.
**Импорт при старте пропускает уже существующий realm.** Перезапуск не применит
изменения к существующим clients/roles. Для существующего окружения обновить
настройки через Admin Console по списку ниже. Не удалять volume БД ради импорта.

## Настройки realm

| Client | Назначение и настройки |
|---|---|
| tiu-media-hub-web | Public; Standard Flow; PKCE S256; без Direct Access Grants и Service Accounts |
| tiu-media-hub-api | Resource server, все login/service flows выключены; владелец API roles |
| tiu-media-hub-worker | Confidential; только Service Accounts, без пользовательских flows |

Web redirect URI: http://localhost:5173/callback; Web Origin: http://localhost:5173.
Для другого frontend изменить redirect URI, web origin и API_CORS_ORIGINS.

У web и worker есть:
- audience mapper: included client audience = tiu-media-hub-api, access token only;
- hardcoded claim mapper: auth_type = user для web, client для worker,
  JSON type String, access token only;
- default client scopes basic/roles, у web также profile/email;
- Full Scope Allowed = OFF;
- scope mappings API roles: web — user/admin, worker — assets:read/collections:read.

Создать пользователя в Admin Console, установить постоянный пароль и назначить
**client role** user клиента tiu-media-hub-api. Для администратора — admin.
Realm role с тем же названием backend игнорирует.

Scope basic обязателен: в этой версии Keycloak он добавляет пользовательский sub
в access token. Без него API корректно отвергнет токен. Это поведение описано в
[Keycloak upgrading guide](https://www.keycloak.org/docs/latest/upgrading/).

Worker service account получает только assets:read и collections:read.
Получить сгенерированный секрет: Clients → tiu-media-hub-worker → Credentials.
Хранить его в SRV_CLIENT_SECRET окружения worker. JSON realm не содержит secret.
Для каждого нового сервиса создать отдельный client/secret и назначить только
нужные capabilities, затем добавить client_id в KEYCLOAK_SERVICE_CLIENT_IDS API.
Сервисы не включаются в пользовательский allowlist.

## Проверка пользователя

SPA использует Keycloak/OIDC adapter: Authorization Code + PKCE S256.
После входа отправить access token в Authorization: Bearer на
GET /api/v1/users/me. ID token и refresh token для этого не подходят.
Password Grant отключён; backend не принимает логин/пароль пользователя.

Для ручной проверки можно использовать OAuth-клиент с PKCE и разрешённым redirect URI.
Автоматический полный flow без ручных действий:

```powershell
uv run python -m tests.check_keycloak
```

Команда использует отдельный временный контейнер на localhost:18081.
Она не проверяет и не меняет существующий realm на 8081.

## Проверка worker

В окружении worker:

```dotenv
SRV_BASE_URL=http://localhost:8000/api/v1/
SRV_TOKEN_URL=http://localhost:8081/realms/tiu-media-hub/protocol/openid-connect/token
SRV_CLIENT_ID=tiu-media-hub-worker
SRV_CLIENT_SECRET=<секрет из Keycloak>
```

```python
from src.core.auth.models import Client
from src.core.services.base import SrvBaseClient, SrvBaseConfig


async def check_worker() -> Client:
    async with SrvBaseClient(SrvBaseConfig()) as client:
        return await client.request_json("GET", "auth/me", Client)
```

GET /api/v1/auth/me должен вернуть type=client, client_id и сервисные роли.
GET /api/v1/users/me с этим токеном возвращает 403.

Обычная проверка bearer не использует секрет worker: API нужны только issuer,
audience, JWKS URL и allowlists. Секрет нужен только вызывающему сервису.

## Переход с прежней конфигурации

1. Добавить audience/auth_type mappers и scopes на web.
2. Перенести назначения user/admin с realm roles на роли клиента API.
3. Создать отдельный worker с Service Accounts и нужными role scope mappings.
4. Обновить конфигурацию API/worker. Старые KEYCLOAK_CLIENT_ID и
   KEYCLOAK_CLIENT_SECRET больше не используются для входящих JWT.
5. Выполнить новый вход в SPA, чтобы получить токены нового формата.
6. Проверить обе /me ручки и отказ при неподходящей роли/типе principal.

В production использовать HTTPS и URL своего домена, а не локальные значения.
Секреты service accounts, пароли и токены не включать в логи или экспорт realm.

# API для фронта

OpenAPI: `http://localhost:8000/docs`, схема для генерации типов — `/openapi.json`.

## Соглашения

* JSON в **camelCase** (DTO с `alias_generator`), query-параметры тоже: `?collectionId=…&personId=…`.
* Авторизация: `Authorization: Bearer <access token Keycloak>` (клиент `tiu-media-hub-web`, PKCE).
* Частичное обновление (`PATCH`): отсутствующее поле не меняется, явный `null` очищает необязательное поле.
* Списки активов — курсорная пагинация: `{items, nextCursor, hasNext}`, параметры `cursor`, `size` (≤200).
* Ошибки: `{"errorCode": "...", "message": "...", "details": ...}`.

| Код | Когда |
|---|---|
| 401 | Нет или неверный токен (`invalid_token`); закрытый портал (`portal_locked`, в `details.access` — тип доступа) |
| 403 | Недостаточно прав (`permission_denied`) |
| 404 | Ресурса нет или нет права его читать |
| 409 | Нарушение правила: неверное значение метаданных, тип файла, непустая коллекция, дубль slug (`invariant_violation`, `invalid_state`, `unique_constraint_violation`) |
| 503 | Keycloak недоступен |

## Группы

| Префикс | Кто |
|---|---|
| `/api/v1` | Пользователи медиатеки |
| `/api/admin/v1` | Администраторы (роль `admin`) |
| `/api/service/v1` | Сервисы (Client Credentials, роль `assets:read`) |
| `/api/public/v1/portals/{slug}` | Посетители порталов (без входа / по паролю / сотрудники) |

## Загрузка файла

```ts
const ticket = await api.post("/uploads", { collectionId, filename: file.name, contentType: file.type, size: file.size });
// новая версия существующего актива: { assetId, ... } вместо collectionId

if (ticket.url) {
  await fetch(ticket.url, { method: "PUT", body: file, headers: ticket.headers });
  await api.post(`/uploads/${ticket.uploadId}/complete`, { title });
} else {
  const parts = [];
  for (const part of ticket.parts) {
    const start = (part.partNumber - 1) * ticket.partSize;
    const response = await fetch(part.url, { method: "PUT", body: file.slice(start, start + ticket.partSize) });
    parts.push({ partNumber: part.partNumber, etag: response.headers.get("ETag") });
  }
  await api.post(`/uploads/${ticket.uploadId}/complete`, { parts, title });
}
```

Ответ `complete` — актив с `version.status = "processing"`. Превью появятся, когда статус станет `ready`
(опрос `GET /assets/{id}`); при `failed` файл доступен только для скачивания.

## Ссылки на медиа

* `version.urls.thumbnail | preview | video | audio` — временные ссылки CDN (живут 1–2 часа), не сохраняйте их;
  при истечении (410) перезапросите актив.
* Оригинал: `GET /assets/{id}/download?versionId=…` → `{url, expiresIn}`.
* Миниатюры лиц и обложки людей — в `thumbnailUrl` / `coverUrl`.

## Видео и речь

* Плеер: `version.urls.video` (H.264 720p, поддерживает перемотку), постер — `preview`.
* Комментарий к моменту: `anchor: {type: "time", start, end}`; к области изображения:
  `anchor: {type: "region", x, y, width, height}` в долях кадра.
* Расшифровка: `GET /assets/{id}/transcript` → сегменты `{start, end, text}`.
* В результатах поиска `matches[].timecode` — момент для перехода.

## Редактор

`POST /assets/{id}/edits` с рецептом → `202 {assetId, versionId}`; результат появится как версия
(`GET /assets/{assetId}/versions`) или новый актив. Координаты в рецепте — доли кадра после поворота,
поэтому предпросмотр по `preview` совпадает с результатом по оригиналу.

## Порталы

* Управление: `/api/v1/portals` (блоки `hero`, `text`, `gallery`, `files`; `published: true` публикует).
* Страница: `GET /api/public/v1/portals/{slug}` — блоки уже содержат активы со ссылками.
* Пароль: `POST /api/public/v1/portals/{slug}/unlock {password}` → токен, далее заголовок `X-Portal-Token`.
* Для доступа `employees` передайте Bearer сотрудника.

# Проверка корректности запуска Keycloak

## Проверка создания realm

1. [Открыть в браузере Keycloak Admin Console](http://localhost:8081)

2. Войти под учётными данными указанными в `.env`

3. Должен появиться realm - `TIU Media Hub`

## Проверка OIDC discovery

```bash
curl http://localhost:8081/realms/tiu-media-hub/.well-known/openid-configuration
```

В ответе должно быть что-то типа того

```bash
{
  "issuer": "http://localhost:8081/realms/tiu-media-hub",
  "authorization_endpoint": "...",
  "token_endpoint": "...",
  "jwks_uri": "...",
  ...
}
```

## Создание тестового пользователя

В Admin Console:

```plain
Realm: tiu-media-hub

Users
  ↓
Create new user
```

Например:

```plain
username: test
email: test@example.com
```

Затем:

```plain
Credentials
  ↓
Set password

Например: test-password

Temporary = OFF.
```

Выдать пользователю роль - `user`


## Как получить access token для пользователя

```bash
export $(grep -v '^#' .env | xargs) && \
curl -X POST \
  "http://localhost:8081/realms/tiu-media-hub/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=$KEYCLOAK_CLIENT_ID" \
  -d "client_secret=$KEYCLOAK_CLIENT_SECRET" \
  -d "username=test" \
  -d "password=test-password" \
  -d "grant_type=password"
```

Ожидаемый ответ

```bash
{
  "access_token": "eyJ...",
  "expires_in": 300,
  "token_type": "Bearer"
}
```

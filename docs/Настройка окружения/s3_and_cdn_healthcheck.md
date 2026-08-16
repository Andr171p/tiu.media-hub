# Проверка работоспособности S3 в связке с локальным CDN

## Проверка MinIO

```bash
curl -i http://localhost:9000/minio/health/ready
```

Должно быть:
```bash
HTTP/1.1 200 OK
Accept-Ranges: bytes
Content-Length: 0
Server: MinIO
Strict-Transport-Security: max-age=31536000; includeSubDomains
Vary: Origin
X-Amz-Id-2: dd9025bab4ad464b049177c95eb6ebf374d3b3fd1af9251148b658df7ac2e3e8
X-Amz-Request-Id: 18CC42698F3D422E
X-Content-Type-Options: nosniff
X-Xss-Protection: 1; mode=block
Date: Sun, 16 Aug 2026 10:29:33 GMT
```

## Проверка Nginx CDN

```bash
curl -i http://localhost:8080/healthz
```

Ожидаемый результат:
```bash
HTTP/1.1 404 Not Found
Connection: Keep-Alive
Server: Embedthis-http
Cache-Control: no-cache
Date: Sun, 16 Aug 2026 10:31:56 GMT
Content-Length: 176
Keep-Alive: timeout=60, max=199

<!DOCTYPE html>
<html><head><title>Not Found</title></head>
<body>
<h2>Access Error: 404 -- Not Found</h2>
<pre>Cannot open document for: /healthz</pre>
</body>
</html>

```

## Загрузка тестового объекта в MinIO

Создание файла
```bash
echo "hello world" > test.txt
```

Загрузка в docker контейнер

```bash
docker cp test.txt tiumedia-hub-minio-1:/tmp/test.txt
```

Загрузка в S3 (имя контейнера и сети заменить на своё).

> Для unix систем убрать флаг - `MSYS_NO_PATHCONV=1`

```bash
MSYS_NO_PATHCONV=1 docker run --rm \
  --network tiumedia-hub_default \
  -v "$(pwd)/test.txt:/tmp/test.txt:ro" \
  --entrypoint /bin/sh \
  minio/mc \
  -c '
    mc alias set local http://minio:9000 dev dev-secret-key &&
    mc cp /tmp/test.txt local/dam-dev/assets/test.txt
  '
```

Ожидаемый результат

```bash
Added `local` successfully.
`/tmp/test.txt` -> `local/dam-dev/assets/test.txt`
┌───────┬─────────────┬──────────┬─────────┐
│ Total │ Transferred │ Duration │ Speed   │
│ 12 B  │ 12 B        │ 00m00s   │ 747 B/s │
└───────┴─────────────┴──────────┴─────────┘
```

Проверка прямого доступа в MinIO

```bash
curl -i http://localhost:9000/dam-dev/assets/test.txt
```

Ожидаемый результат

```bash
HTTP/1.1 200 OK
Accept-Ranges: bytes
Content-Length: 12
Content-Type: text/plain
ETag: "6f5902ac237024bdd0c176cb93063dc4"
Last-Modified: Sun, 16 Aug 2026 12:52:05 GMT
Server: MinIO
Strict-Transport-Security: max-age=31536000; includeSubDomains
Vary: Origin
Vary: Accept-Encoding
X-Amz-Id-2: dd9025bab4ad464b049177c95eb6ebf374d3b3fd1af9251148b658df7ac2e3e8
X-Amz-Request-Id: 18CC4A5176B0CBF3
X-Content-Type-Options: nosniff
X-Ratelimit-Limit: 1995
X-Ratelimit-Remaining: 1995
X-Xss-Protection: 1; mode=block
Date: Sun, 16 Aug 2026 12:54:25 GMT

hello world
```

Проверка в CDN

```bash
curl -i http://localhost:8080/assets/test.txt
```

Ожидаемый результат

```bash
HTTP/1.1 200 OK
Server: nginx/1.31.3
Date: Sun, 16 Aug 2026 13:02:54 GMT
Content-Type: text/plain
Content-Length: 12
Connection: keep-alive
ETag: "6f5902ac237024bdd0c176cb93063dc4"
Last-Modified: Sun, 16 Aug 2026 13:02:43 GMT
Strict-Transport-Security: max-age=31536000; includeSubDomains
Vary: Origin
Vary: Accept-Encoding
X-Amz-Id-2: dd9025bab4ad464b049177c95eb6ebf374d3b3fd1af9251148b658df7ac2e3e8
X-Amz-Request-Id: 18CC4AC7C82B0C17
X-Content-Type-Options: nosniff
X-Ratelimit-Limit: 1983
X-Ratelimit-Remaining: 1983
X-Xss-Protection: 1; mode=block
Cache-Control: public, max-age=31536000, immutable
X-Cache-Status: MISS
Accept-Ranges: bytes

hello world

```

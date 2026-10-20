#!/bin/sh
# Создаёт бакеты. Производные (превью, прокси) доступны анонимно на чтение, но только внутри
# сети Docker: снаружи их отдаёт nginx по подписанной ссылке. Оригиналы — только по presigned URL.
set -eu

mc alias set local "http://rustfs:9000" "$S3_ACCESS_KEY" "$S3_SECRET_KEY"
mc mb --ignore-existing "local/$S3_ORIGINALS_BUCKET"
mc mb --ignore-existing "local/$S3_RENDITIONS_BUCKET"
mc anonymous set download "local/$S3_RENDITIONS_BUCKET"

echo "Storage initialized: $S3_ORIGINALS_BUCKET, $S3_RENDITIONS_BUCKET"

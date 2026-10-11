#!/bin/sh
# Инициализация хранилища: бакет закрыт, анонимное чтение разрешено только производным
# (renditions/*) и только CDN, который передаёт секретный Referer. Оригиналы — только по presigned URL.
set -eu

mc alias set local "http://minio:9000" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb --ignore-existing "local/$S3_BUCKET"

cat > /tmp/policy.json <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"AWS": ["*"]},
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::$S3_BUCKET/renditions/*"],
      "Condition": {"StringEquals": {"aws:Referer": ["cdn:$CDN_SECRET"]}}
    }
  ]
}
POLICY

mc anonymous set-json /tmp/policy.json "local/$S3_BUCKET"
echo "Storage initialized: bucket $S3_BUCKET"

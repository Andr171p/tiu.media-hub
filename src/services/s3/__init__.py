from src.core.s3.client import S3Client
from src.core.s3.config import S3Config

s3_config = S3Config()
s3_client = S3Client(s3_config)

__all__ = ["s3_client"]

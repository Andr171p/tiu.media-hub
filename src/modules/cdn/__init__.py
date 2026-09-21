from src.core.cdn.client import CdnClient
from src.core.cdn.config import CdnConfig

cdn_config = CdnConfig()
cdn_client = CdnClient(cdn_config)

__all__ = ["cdn_client"]

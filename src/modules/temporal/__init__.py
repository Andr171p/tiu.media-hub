from src.core.temporal.client import TemporalClient
from src.core.temporal.config import TemporalConfig

temporal_config = TemporalConfig()
temporal_client = TemporalClient(temporal_config)

__all__ = ["temporal_client"]

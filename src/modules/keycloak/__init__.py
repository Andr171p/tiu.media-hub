from src.core.keycloak.client import KeycloakClient
from src.core.keycloak.config import KeycloakConfig

keycloak_config = KeycloakConfig()
keycloak_client = KeycloakClient(keycloak_config)

__all__ = ["keycloak_client"]

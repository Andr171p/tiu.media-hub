from src.core.keycloak.client import KeycloakClient
from src.core.keycloak.config import KeycloakConfig
from src.core.keycloak.exceptions import KeycloakError

keycloak_config = KeycloakConfig()  # type: ignore
keycloak_client = KeycloakClient(keycloak_config)

__all__ = ["KeycloakError", "keycloak_client"]

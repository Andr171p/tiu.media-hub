import jwt

from src.core.auth import AuthClient, AuthUser, UnauthorizedError

from .claims import build_auth_from_claims
from .config import KeycloakConfig
from .jwks import KeycloakJwksClient

_REQUIRED_CLAIMS = ("exp", "iat", "iss", "aud", "sub", "azp", "typ")


def _get_signing_header(token: str, allowed_algorithms: tuple[str, ...]) -> tuple[str, str]:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid token header.") from None

    kid, algorithm = header.get("kid"), header.get("alg")

    if not isinstance(kid, str) or not kid:
        raise UnauthorizedError("Token does not contain a signing key ID.")

    if algorithm not in allowed_algorithms:
        raise UnauthorizedError("Unsupported signing algorithm.")

    return kid, algorithm


class KeycloakClient:
    """Локальная проверка access-токенов Keycloak по закешированным публичным ключам."""

    def __init__(self, config: KeycloakConfig) -> None:
        self._config = config
        self._jwks_client = KeycloakJwksClient(config)

    async def verify_token(self, token: str) -> AuthUser | AuthClient:
        kid, algorithm = _get_signing_header(token, self._config.algorithms)

        key = await self._jwks_client.get_key(kid)
        if key.algorithm_name != algorithm:
            raise UnauthorizedError("Signing algorithm does not match the key.")

        try:
            payload = jwt.decode(
                token,
                key=key,
                algorithms=list(self._config.algorithms),
                audience=self._config.audience,
                issuer=str(self._config.issuer_url).rstrip("/"),
                leeway=self._config.clock_skew,
                options={"require": list(_REQUIRED_CLAIMS)},
            )
        except jwt.InvalidTokenError as exc:
            raise UnauthorizedError("Invalid access token.") from exc

        return build_auth_from_claims(payload, self._config)

    async def close(self) -> None:
        await self._jwks_client.close()


__all__ = ["KeycloakClient"]

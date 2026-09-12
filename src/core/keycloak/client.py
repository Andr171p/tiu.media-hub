import jwt

from src.core.auth.exceptions import AuthenticationError
from src.core.auth.models import Auth

from .claims import build_auth_from_claims
from .config import KeycloakConfig
from .jwks import KeycloakJwksClient

_REQUIRED_CLAIMS = (
    "exp",
    "iat",
    "iss",
    "aud",
    "sub",
    "azp",
)


def _get_signing_header(token: str, allowed_algorithms: tuple[str, ...]) -> tuple[str, str]:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid signing header.") from None

    kid, algorithm = header.get("kid"), header.get("alg")

    if not isinstance(kid, str) or not kid:
        raise AuthenticationError("Token does not contain a signing key ID.")

    if algorithm not in allowed_algorithms:
        raise AuthenticationError("Unsupported signing algorithm.")

    return kid, algorithm


class KeycloakClient:
    def __init__(self, config: KeycloakConfig) -> None:
        self._config = config
        self._jwks_client = KeycloakJwksClient(config)

    async def verify_token(self, token: str) -> Auth:
        kid, algorithm = _get_signing_header(token, self._config.algorithms)

        key = await self._jwks_client.get_key(kid)

        if key.algorithm_name != algorithm:
            raise AuthenticationError("Signing algorithm does not match the key.")

        try:
            payload = jwt.decode(
                token,
                key=key,
                algorithms=self._config.algorithms,
                audience=self._config.audience,
                issuer=str(self._config.issuer_url),
                leeway=self._config.clock_skew,
                options={"require": list(_REQUIRED_CLAIMS)},
            )
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("Invalid access token.") from exc

        return build_auth_from_claims(payload, self._config)

    async def close(self) -> None:
        await self._jwks_client.close()

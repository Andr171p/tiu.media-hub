from dataclasses import dataclass

from ddf.domain.models import Entity


@dataclass(kw_only=True)
class User(Entity):
    """Профиль сотрудника из Keycloak (``id`` = ``sub``): для авторов, участников и поиска людей."""

    username: str | None = None
    email: str | None = None
    full_name: str | None = None

    @property
    def display_name(self) -> str:
        return self.full_name or self.username or self.email or str(self.id)

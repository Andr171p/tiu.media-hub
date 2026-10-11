from sqlalchemy.orm import Mapped

from src.core.database import Base
from src.core.database.types import DatetimeTz, StrNull


class User(Base):
    """
    Локальный профиль пользователя Keycloak. ``id`` совпадает с ``sub`` токена.
    Обновляется при входе: по нему ищут участников коллекций и показывают авторов.
    """

    __tablename__ = "users"

    email: Mapped[StrNull]
    username: Mapped[StrNull]
    full_name: Mapped[StrNull]
    last_seen_at: Mapped[DatetimeTz]

    @property
    def display_name(self) -> str:
        return self.full_name or self.username or self.email or str(self.id)

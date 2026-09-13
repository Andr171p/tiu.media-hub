from src.core.auth.models import User

from .models import Asset


def is_asset_author(asset: Asset, user: User) -> bool:
    return asset.author_id == user.id

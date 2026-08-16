from src.core.assets.models import Asset
from src.core.assets.schemas import AssetCreate, AssetUpdate
from src.core.common.crud import Crud

crud = Crud[
    Asset,
    AssetCreate,
    AssetUpdate,
    None, None, None, None,
](Asset)

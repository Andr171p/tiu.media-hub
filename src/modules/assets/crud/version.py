from src.core.assets.models import AssetVersion
from src.core.assets.schemas import AssetVersionCreate, AssetVersionUpdate
from src.core.common.crud import Crud

crud = Crud[
    AssetVersion,
    AssetVersionCreate,
    AssetVersionUpdate,
    None, None, None, None,
](AssetVersion)

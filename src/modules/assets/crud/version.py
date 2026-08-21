from src.core.assets.models import AssetVersion
from src.core.assets.schemas import CreateAssetVersionDTO, UpdateAssetVersionDTO
from src.core.common.crud import Crud

crud = Crud[
    AssetVersion,
    CreateAssetVersionDTO,
    UpdateAssetVersionDTO,
    None, None, None, None,
](AssetVersion)

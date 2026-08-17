from src.core.assets.models import AssetVersion
from src.core.assets.schemas import AssetVersionCreate
from src.core.common.crud import Crud

crud = Crud[
    AssetVersion,
    AssetVersionCreate,
    AssetUpdate,
    None, None, None, None,
](
    Asset,
    create_wrapper=create_wrapper,
)
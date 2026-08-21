from temporalio import activity


@activity.defn(name="validate_upload")
async def validate_upload(): ...


@activity.defn(name="extract_metadata")
async def extract_metadata(): ...


@activity.defn(name="calculate_checksum")
async def calculate_checksum(): ...


@activity.defn(name="create_asset_version")
async def create_asset_version(): ...


@activity.defn(name="generate_thumbnail")
async def generate_thumbnail(): ...


@activity.defn(name="generate_preview")
async def generate_preview(): ...


@activity.defn(name="generate_watermark")
async def generate_watermark(): ...

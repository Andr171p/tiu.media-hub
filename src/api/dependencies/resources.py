from typing import Annotated

from fastapi import Depends, Request

from src.core.cdn import CdnClient
from src.core.s3 import S3Client
from src.modules.media import UploadConfig
from src.modules.search import AssetSearch


def get_s3(request: Request) -> S3Client:
    return request.app.state.s3


def get_cdn(request: Request) -> CdnClient:
    return request.app.state.cdn


def get_search(request: Request) -> AssetSearch:
    return request.app.state.search


def get_upload_config(request: Request) -> UploadConfig:
    return request.app.state.upload_config


S3Dep = Annotated[S3Client, Depends(get_s3)]
CdnDep = Annotated[CdnClient, Depends(get_cdn)]
SearchDep = Annotated[AssetSearch, Depends(get_search)]
UploadConfigDep = Annotated[UploadConfig, Depends(get_upload_config)]

__all__ = ["CdnDep", "S3Dep", "SearchDep", "UploadConfigDep"]

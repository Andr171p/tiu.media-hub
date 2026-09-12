"""Keep the domain service importable without initializing HTTP/auth infrastructure."""


def __getattr__(name: str):
    if name == "asset_crud":
        from .crud import asset_crud

        return asset_crud
    if name == "asset_depends":
        from .dependencies import asset_depends

        return asset_depends
    raise AttributeError(name)

__all__ = ["asset_crud", "asset_depends"]

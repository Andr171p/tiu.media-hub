"""Run only against a disposable DB supplied via ASSET_TEST_DATABASE_URL.

Each test owns a random schema; no existing application tables are touched.
"""

import asyncio
import os
import unittest
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.assets.file_dtos import DerivativeResponse, VersionResponse
from src.core.assets.metadata import MetadataSchema
from src.core.assets.models import Asset, AssetDerivative, AssetMetadataProfile, AssetVersion
from src.core.database.base import Base
from src.modules.assets.services import (
    AssetConflictError,
    create_derivative,
    create_metadata_profile,
    create_version,
    publish_version,
    replace_custom_metadata,
)

from test_asset_metadata import derivative, original

DATABASE_URL = os.environ.get("ASSET_TEST_DATABASE_URL")
ASSET_TABLES = [model.__table__ for model in
                (AssetMetadataProfile, Asset, AssetVersion, AssetDerivative)]


@unittest.skipUnless(DATABASE_URL, "Set ASSET_TEST_DATABASE_URL to a disposable PostgreSQL DB")
class AssetPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.schema = "asset_test_" + uuid4().hex
        self.admin = create_async_engine(DATABASE_URL)
        async with self.admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.engine = create_async_engine(
            DATABASE_URL, connect_args={"server_settings": {"search_path": self.schema}}
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(lambda sync: Base.metadata.create_all(sync, tables=ASSET_TABLES))

    async def asyncTearDown(self):
        await self.engine.dispose()
        async with self.admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        await self.admin.dispose()

    async def new_asset(self):
        async with self.sessions.begin() as session:
            asset = Asset(title="Test asset")
            session.add(asset)
            await session.flush()
            return asset.id

    async def test_parallel_versions_and_retry(self):
        asset_id = await self.new_asset()
        first, second = original(), original()

        async def append(dto):
            async with self.sessions.begin() as session:
                return await create_version(session, asset_id, dto)

        versions = await asyncio.gather(append(first), append(second))
        self.assertEqual({v.version for v in versions}, {1, 2})
        repeated = await append(first)
        self.assertEqual(repeated.id, versions[0].id)
        with self.assertRaises(AssetConflictError):
            await append(first.model_copy(update={"checksum": "c" * 64}))

    async def test_publish_rejects_foreign_and_stale_versions(self):
        asset_id, other_id = await self.new_asset(), await self.new_asset()
        async with self.sessions.begin() as session:
            first = await create_version(session, asset_id, original())
            second = await create_version(session, asset_id, original())
            await publish_version(session, asset_id, second.id, expected_current_version_id=None)
            with self.assertRaises(AssetConflictError):
                await publish_version(session, asset_id, first.id, expected_current_version_id=None)
            with self.assertRaises(LookupError):
                await publish_version(session, other_id, first.id, expected_current_version_id=None)
            # An explicit rollback retains sequence and original records.
            asset = await publish_version(session, asset_id, first.id,
                                          expected_current_version_id=second.id)
            self.assertEqual(asset.current_version_id, first.id)
            third = await create_version(session, asset_id, original())
            self.assertEqual(third.version, 3)
        async with self.sessions.begin() as session:
            with self.assertRaises(IntegrityError), session.no_autoflush:
                async with session.begin_nested():
                    other = await session.get(Asset, other_id)
                    other.current_version_id = first.id
                    await session.flush()

    async def test_derivative_variants_and_public_responses(self):
        asset_id = await self.new_asset()
        async with self.sessions.begin() as session:
            version = await create_version(session, asset_id, original())
            dto = derivative()
            small = await create_derivative(session, version.id, dto)
            repeated = await create_derivative(session, version.id, dto)
            large = await create_derivative(session, version.id, derivative(profile="large"))
            revised = await create_derivative(session, version.id, derivative(recipe_version=2))
            self.assertEqual(small.id, repeated.id)
            self.assertEqual(len({small.id, large.id, revised.id}), 3)
            with self.assertRaises(AssetConflictError):
                await create_derivative(session, version.id, derivative())
            for response in (VersionResponse.model_validate(version),
                             DerivativeResponse.model_validate(small)):
                self.assertNotIn("storage_key", response.model_dump())
                self.assertNotIn("raw_metadata", response.model_dump())

    async def test_custom_metadata_profile_revisions_and_clearing(self):
        asset_id = await self.new_asset()
        schema = MetadataSchema.model_validate({"fields": [
            {"key": "year", "label": "Year", "type": "integer", "required": True},
        ]})
        async with self.sessions.begin() as session:
            profile = await create_metadata_profile(session, "events", 1, schema)
            asset = await replace_custom_metadata(session, asset_id, profile.id, {"year": 2026})
            await create_metadata_profile(session, "events", 2, MetadataSchema())
            self.assertEqual(asset.metadata_profile_id, profile.id)
            with self.assertRaises(ValueError):
                await replace_custom_metadata(session, asset_id, profile.id, {"year": True})
            self.assertEqual(asset.custom_metadata, {"year": 2026})
            await replace_custom_metadata(session, asset_id, None, {})
        async with self.sessions() as session:
            asset = await session.get(Asset, asset_id)
            self.assertIsNone(asset.metadata_profile_id)
            self.assertEqual(asset.custom_metadata, {})

    async def test_database_checks_on_direct_writes(self):
        asset_id = await self.new_asset()
        async with self.sessions.begin() as session:
            version = await create_version(session, asset_id, original())
            for invalid in ("size = -1", "width = 0", "duration = 'NaN'::float8",
                            "checksum = 'etag'", "version = 0"):
                with self.subTest(invalid=invalid), self.assertRaises(IntegrityError):
                    async with session.begin_nested():
                        await session.execute(text(f"UPDATE asset_versions SET {invalid} WHERE id = :id"),
                                              {"id": version.id})

    async def test_migration_preserves_legacy_data(self):
        async with self.engine.begin() as connection:
            await connection.run_sync(lambda sync: Base.metadata.drop_all(sync, tables=ASSET_TABLES))
        raw = await self.engine.raw_connection()
        try:
            await raw.driver_connection.execute(
                Path("tests/fixtures/assets_legacy.sql").read_text(encoding="utf-8")
            )
            await raw.driver_connection.execute(
                Path("src/modules/assets/migrations/001_flexible_assets.sql").read_text(encoding="utf-8")
            )
        finally:
            raw.close()
        async with self.sessions.begin() as session:
            asset = await session.get(Asset, "00000000-0000-0000-0000-000000000001")
            version = await session.get(AssetVersion, asset.current_version_id)
            self.assertEqual(version.raw_metadata, {"EXIF:Model": "Legacy Camera"})
            self.assertEqual(VersionResponse.model_validate(version).media_details.kind, "image")
            legacy = await session.get(AssetDerivative, "00000000-0000-0000-0000-000000000003")
            self.assertEqual(legacy.parameters, {"legacy_metadata": {"unknown": 42}})
            self.assertEqual(DerivativeResponse.model_validate(legacy).type_, "thumbnail")
            await create_derivative(session, version.id, derivative(profile="large"))

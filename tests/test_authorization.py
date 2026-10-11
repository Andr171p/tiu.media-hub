import unittest
from itertools import product
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException

from src.core.assets.authorization import check_asset_access
from src.core.assets.models import Asset
from src.core.assets.dtos import CreateAssetDTO, UploadAssetDTO
from src.core.auth.models import Client, User
from src.core.auth.exceptions import AuthorizationError
from src.core.collections.authorization import (
    CollectionAccess,
    CollectionPermission,
    check_collection_access,
)
from src.core.collections.models import MemberRole
from src.modules.assets import uploading
from src.modules.assets.crud.asset import create_wrapper
from src.modules.auth.dependencies import get_current_client, get_current_user, require_roles


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.owner = User(id=uuid4(), roles={"creator"})
        self.stranger = User(id=uuid4(), roles={"creator"})

    def test_role_requirements(self):
        user = User(id=uuid4(), roles={"read", "write"})
        self.assertIs(require_roles("read", "admin")(user), user)
        self.assertIs(require_roles("read", "write", all_required=True)(user), user)
        for dependency in (
            require_roles("admin"),
            require_roles("read", "admin", all_required=True),
        ):
            with self.assertRaises(HTTPException) as raised:
                dependency(user)
            self.assertEqual(raised.exception.status_code, 403)
        with self.assertRaises(ValueError):
            require_roles()

    def test_principal_types_are_enforced(self):
        client = Client(client_id="worker")
        self.assertIs(get_current_client(client), client)
        self.assertIs(get_current_user(self.owner), self.owner)
        with self.assertRaises(HTTPException):
            get_current_user(client)
        with self.assertRaises(HTTPException):
            get_current_client(self.owner)

    def test_collection_permission_matrix(self):
        for role, permission in product((None, *MemberRole), CollectionPermission):
            access = CollectionAccess(owner_id=self.owner.id, is_active=True, member_role=role)
            allowed = role == MemberRole.CONTRIBUTOR and permission != CollectionPermission.MANAGE
            allowed |= role == MemberRole.VIEWER and permission == CollectionPermission.READ
            with self.subTest(role=role, permission=permission):
                check_collection_access(self.owner, access, permission)
                if allowed:
                    check_collection_access(self.stranger, access, permission)
                else:
                    with self.assertRaises(AuthorizationError):
                        check_collection_access(self.stranger, access, permission)

    def test_inactive_collections_and_service_scope(self):
        reader = Client(client_id="worker", roles={"collections:read", "admin"})
        active = CollectionAccess(self.owner.id, True)
        check_collection_access(reader, active, CollectionPermission.READ)
        for permission in (CollectionPermission.CONTRIBUTE, CollectionPermission.MANAGE):
            with self.assertRaises(AuthorizationError):
                check_collection_access(reader, active, permission)
        for principal in (self.owner, reader):
            with self.assertRaises(AuthorizationError):
                check_collection_access(
                    principal, CollectionAccess(self.owner.id, False), CollectionPermission.READ
                )

    def test_asset_author_boundary(self):
        for write in (False, True):
            check_asset_access(self.owner, self.owner.id, write=write)
            with self.assertRaises(AuthorizationError):
                check_asset_access(self.stranger, self.owner.id, write=write)
            with self.assertRaises(AuthorizationError):
                check_asset_access(self.owner, None, write=write)

    def test_service_asset_role_is_read_only(self):
        reader = Client(client_id="worker", roles={"assets:read", "admin"})
        check_asset_access(reader, self.owner.id)
        with self.assertRaises(AuthorizationError):
            check_asset_access(reader, self.owner.id, write=True)
        with self.assertRaises(AuthorizationError):
            check_asset_access(Client(client_id="worker"), self.owner.id)


class AssetAuthorTests(unittest.IsolatedAsyncioTestCase):
    async def test_author_is_taken_from_authenticated_user(self):
        user = User(id=uuid4(), roles={"creator"})
        persist = AsyncMock()
        await create_wrapper(persist, CreateAssetDTO(title="Asset"), user)
        persist.assert_awaited_once_with({"author_id": user.id})

    async def test_no_role_cannot_create_asset(self):
        persist = AsyncMock()
        with self.assertRaises(AuthorizationError):
            await create_wrapper(persist, CreateAssetDTO(title="Asset"), User(id=uuid4()))
        persist.assert_not_awaited()

    async def test_foreign_asset_upload_is_denied_before_external_effects(self):
        asset = Asset(id=uuid4(), author_id=uuid4(), title="Foreign asset")
        user = User(id=uuid4(), roles={"creator"})
        session = AsyncMock()
        with (
            patch.object(uploading.asset_crud, "read", new=AsyncMock(return_value=asset)),
            patch.object(uploading.s3_client, "create_upload_url", new=AsyncMock()) as presign,
            patch.object(
                uploading.temporal_client, "complete_asset_upload", new=AsyncMock()
            ) as signal,
        ):
            with self.assertRaises(AuthorizationError):
                await uploading.init_upload(
                    session,
                    asset.id,
                    UploadAssetDTO(filename="photo.jpg", mime_type="image/jpeg", size=100),
                    user,
                )
            with self.assertRaises(AuthorizationError):
                await uploading.complete_upload(session, asset.id, uuid4(), user)
        presign.assert_not_awaited()
        signal.assert_not_awaited()
        session.commit.assert_not_awaited()

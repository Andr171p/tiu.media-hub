"""initial dam schema

Revision ID: b643405daa69
Revises:
Create Date: 2026-10-12 02:55:35.104325
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b643405daa69"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stored_objects",
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False, comment="Заявленный при загрузке MIME-тип"),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Последняя успешная проверка целостности",
        ),
        sa.Column(
            "integrity_error", sa.String(), nullable=True, comment="Результат последней неуспешной проверки"
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_stored_objects_sha256_hex")),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_stored_objects_size_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stored_objects")),
        sa.UniqueConstraint("sha256", "size_bytes", name=op.f("uq_stored_objects_sha256_size_bytes")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_stored_objects_storage_key")),
    )
    op.create_table(
        "tags",
        sa.Column(
            "name",
            sa.String(),
            nullable=False,
            comment="Нормализованное имя: нижний регистр, без лишних пробелов",
        ),
        sa.Column("auto_assign", sa.Boolean(), nullable=False),
        sa.Column(
            "prompt",
            sa.String(),
            nullable=True,
            comment="Описание для автотегирования, если имени недостаточно",
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tags")),
        sa.UniqueConstraint("name", name=op.f("uq_tags_name")),
    )
    op.create_index(op.f("ix_tags_auto_assign"), "tags", ["auto_assign"], unique=False)
    op.create_table(
        "users",
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_table(
        "collections",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column(
            "visibility",
            sa.Enum("public", "private", name="visibility", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_collections_owner_id_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collections")),
    )
    op.create_index(op.f("ix_collections_owner_id"), "collections", ["owner_id"], unique=False)
    op.create_table(
        "upload_sessions",
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "completed", "expired", name="uploadstatus", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["object_id"],
            ["stored_objects.id"],
            name=op.f("fk_upload_sessions_object_id_stored_objects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            name=op.f("fk_upload_sessions_uploaded_by_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_upload_sessions")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_upload_sessions_storage_key")),
    )
    op.create_index(op.f("ix_upload_sessions_status"), "upload_sessions", ["status"], unique=False)
    op.create_index(op.f("ix_upload_sessions_uploaded_by"), "upload_sessions", ["uploaded_by"], unique=False)
    op.create_table(
        "assets",
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum("image", "document", "other", name="assetkind", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("active", "archived", name="assetstatus", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("custom_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("license", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name=op.f("fk_assets_author_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["collections.id"],
            name=op.f("fk_assets_collection_id_collections"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
    )
    op.create_index(op.f("ix_assets_author_id"), "assets", ["author_id"], unique=False)
    op.create_index(
        "ix_assets_collection_id_created_at", "assets", ["collection_id", "created_at"], unique=False
    )
    op.create_table(
        "collection_members",
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("member", "moderator", name="memberrole", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["collections.id"],
            name=op.f("fk_collection_members_collection_id_collections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_collection_members_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_members")),
        sa.UniqueConstraint(
            "collection_id", "user_id", name=op.f("uq_collection_members_collection_id_user_id")
        ),
    )
    op.create_index(op.f("ix_collection_members_user_id"), "collection_members", ["user_id"], unique=False)
    op.create_table(
        "asset_tags",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source",
            sa.Enum("manual", "auto", name="tagsource", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=True, comment="Уверенность автотегирования, 0..1"),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["assets.id"], name=op.f("fk_asset_tags_asset_id_assets"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tags.id"], name=op.f("fk_asset_tags_tag_id_tags"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_tags")),
        sa.UniqueConstraint("asset_id", "tag_id", name=op.f("uq_asset_tags_asset_id_tag_id")),
    )
    op.create_index(op.f("ix_asset_tags_tag_id"), "asset_tags", ["tag_id"], unique=False)
    op.create_table(
        "asset_versions",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "source_version_id",
            sa.Uuid(),
            nullable=True,
            comment="Версия, из которой получена эта (правка в редакторе)",
        ),
        sa.Column(
            "status",
            sa.Enum("processing", "ready", "failed", name="versionstatus", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("error", sa.TEXT(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, comment="Запусков обработки"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "extracted_text", sa.TEXT(), nullable=True, comment="Текст документа для полнотекстового поиска"
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("number > 0", name=op.f("ck_asset_versions_number_positive")),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["assets.id"], name=op.f("fk_asset_versions_asset_id_assets"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_asset_versions_created_by_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["object_id"],
            ["stored_objects.id"],
            name=op.f("fk_asset_versions_object_id_stored_objects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["asset_versions.id"],
            name=op.f("fk_asset_versions_source_version_id_asset_versions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_versions")),
        sa.UniqueConstraint("asset_id", "number", name=op.f("uq_asset_versions_asset_id_number")),
        sa.UniqueConstraint("asset_id", "object_id", name=op.f("uq_asset_versions_asset_id_object_id")),
    )
    op.create_index(op.f("ix_asset_versions_status"), "asset_versions", ["status"], unique=False)
    op.create_table(
        "renditions",
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("thumbnail", "preview", name="renditionkind", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["asset_versions.id"],
            name=op.f("fk_renditions_version_id_asset_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_renditions")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_renditions_storage_key")),
        sa.UniqueConstraint("version_id", "kind", name=op.f("uq_renditions_version_id_kind")),
    )
    # Циклическая ссылка assets <-> asset_versions: внешний ключ добавляется после обеих таблиц
    op.create_foreign_key(
        op.f("fk_assets_current_version_id_asset_versions"),
        "assets",
        "asset_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_assets_current_version_id_asset_versions"), "assets", type_="foreignkey")
    op.drop_table("renditions")
    op.drop_index(op.f("ix_asset_versions_status"), table_name="asset_versions")
    op.drop_table("asset_versions")
    op.drop_index(op.f("ix_asset_tags_tag_id"), table_name="asset_tags")
    op.drop_table("asset_tags")
    op.drop_index(op.f("ix_collection_members_user_id"), table_name="collection_members")
    op.drop_table("collection_members")
    op.drop_index("ix_assets_collection_id_created_at", table_name="assets")
    op.drop_index(op.f("ix_assets_author_id"), table_name="assets")
    op.drop_table("assets")
    op.drop_index(op.f("ix_upload_sessions_uploaded_by"), table_name="upload_sessions")
    op.drop_index(op.f("ix_upload_sessions_status"), table_name="upload_sessions")
    op.drop_table("upload_sessions")
    op.drop_index(op.f("ix_collections_owner_id"), table_name="collections")
    op.drop_table("collections")
    op.drop_table("users")
    op.drop_index(op.f("ix_tags_auto_assign"), table_name="tags")
    op.drop_table("tags")
    op.drop_table("stored_objects")

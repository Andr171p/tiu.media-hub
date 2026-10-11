import unittest
from uuid import uuid4

from pydantic import ValidationError

from src.core.assets.file_dtos import CreateDerivativeDTO, CreateVersionDTO
from src.core.assets.metadata import ExtractionMetadata, MetadataSchema
from src.core.assets.utils import build_derivative_storage_key


def original(**overrides):
    return CreateVersionDTO.model_validate({
        "source_operation_id": str(uuid4()), "original_filename": "photo.jpg",
        "storage_key": str(uuid4()), "content_type": "image/jpeg", "size": 123,
        "checksum": "a" * 64, "type_": "image", "media_details": {"kind": "image"},
        **overrides,
    })


def derivative(**overrides):
    return CreateDerivativeDTO.model_validate({
        "storage_key": str(uuid4()), "content_type": "image/webp", "size": 12,
        "checksum": "b" * 64, "type_": "thumbnail", "profile": "small",
        "recipe_version": 1, "media_details": {"kind": "image"}, **overrides,
    })


class MetadataTests(unittest.TestCase):
    def test_polymorphic_media_and_unknown_fields(self):
        for kind in ("image", "audio", "video", "document", "other"):
            self.assertEqual(original(type_=kind, media_details={"kind": kind}).type_, kind)
        for details in ({"kind": "image", "iso": -1}, {"kind": "audio"},
                        {"kind": "image", "camera_typo": "X"}):
            with self.subTest(details=details), self.assertRaises(ValidationError):
                original(media_details=details)

    def test_invalid_technical_facts(self):
        for invalid in ({"size": -1}, {"width": 0}, {"checksum": "etag"},
                        {"duration": float("nan")}, {"duration": float("inf")}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                original(**invalid)
        with self.assertRaises(ValidationError):
            original(type_="video", media_details={"kind": "video", "streams": [
                {"index": 0, "kind": "video"}, {"index": 0, "kind": "audio"},
            ]})

    def test_raw_metadata_retains_namespaces_unknown_tags_and_warnings(self):
        snapshot = ExtractionMetadata.model_validate({
            "extractor": "exiftool", "extractor_version": "13",
            "extracted_at": "2026-09-12T10:00:00Z",
            "tags": {"EXIF:Model": "Camera", "Vendor:Unknown": [1, {"x": True}]},
            "warnings": ["EXIF timestamp has no timezone"],
        })
        self.assertEqual(snapshot.tags["Vendor:Unknown"], [1, {"x": True}])
        self.assertEqual(snapshot.normalization_version, 1)

    def test_custom_fields_strict_validation(self):
        schema = MetadataSchema.model_validate({"fields": [
            {"key": "year", "label": "Year", "type": "integer", "required": True},
            {"key": "topics", "label": "Topics", "type": "choice", "multiple": True,
             "choices": ["science", "sport"]},
            {"key": "date", "label": "Date", "type": "date"},
        ]})
        good = {"year": 2026, "topics": ["science"], "date": "2026-09-12"}
        self.assertEqual(schema.validate_values(good), good)
        for invalid in ({}, {"year": True}, {"year": "2026"}, {"year": None},
                        {"year": 2026, "surprise": 1}, {"year": 2026, "topics": "science"},
                        {"year": 2026, "topics": ["unknown"]},
                        {"year": 2026, "date": "2026-02-30"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                schema.validate_values(invalid)

    def test_invalid_schema_definition(self):
        field = {"key": "x", "label": "X", "type": "text"}
        for fields in ([field, field], [{**field, "type": "choice"}],
                       [{**field, "choices": ["x"]}]):
            with self.assertRaises(ValidationError):
                MetadataSchema.model_validate({"fields": fields})

    def test_derivative_paths_do_not_collide(self):
        asset_id, version_id = uuid4(), uuid4()
        keys = {build_derivative_storage_key(
            asset_id=asset_id, version_id=version_id, derivative_type="thumbnail",
            profile=profile, recipe_version=revision,
        ) for profile in ("small", "large") for revision in (1, 2)}
        self.assertEqual(len(keys), 4)
        with self.assertRaises(ValueError):
            build_derivative_storage_key(asset_id=asset_id, version_id=version_id,
                                         derivative_type="thumbnail", profile="../other")

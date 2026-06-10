"""Tests for the migration module — Firestore schema migration framework.

Covers register_migration decorator, apply_migrations with various
version scenarios, and get_migration_status.
"""

import logging
from unittest.mock import patch

import pytest

from app.services.migration import (
    register_migration,
    apply_migrations,
    get_migration_status,
    _MIGRATIONS,
    _CURRENT_SCHEMA_VERSION,
)

# Use a target version high enough to trigger all test migrations
_TARGET_VERSION = 10


class TestRegisterMigration:
    """Tests for the register_migration decorator."""

    def setup_method(self) -> None:
        """Clear the migration registry before each test."""
        _MIGRATIONS.clear()

    def test_register_migration_adds_function_to_registry(self) -> None:
        """Verify register_migration stores the decorated function."""

        @register_migration(2)
        def migrate_v2(doc: dict) -> dict:
            doc["schema_version"] = 2
            return doc

        assert 2 in _MIGRATIONS
        assert _MIGRATIONS[2] is migrate_v2

    def test_register_migration_preserves_function(self) -> None:
        """Verify the decorated function is returned unchanged."""

        @register_migration(3)
        def migrate_v3(doc: dict) -> dict:
            doc["new_field"] = True
            return doc

        # The function should still be callable
        result = migrate_v3({"schema_version": 1})
        assert result["new_field"] is True

    def test_register_multiple_versions(self) -> None:
        """Verify multiple migrations can be registered."""

        @register_migration(2)
        def m2(doc: dict) -> dict:
            return doc

        @register_migration(3)
        def m3(doc: dict) -> dict:
            return doc

        assert 2 in _MIGRATIONS
        assert 3 in _MIGRATIONS


class TestApplyMigrations:
    """Tests for the apply_migrations function."""

    def setup_method(self) -> None:
        """Clear the migration registry before each test."""
        _MIGRATIONS.clear()

    def test_no_migrations_returns_doc_unchanged(self) -> None:
        """Verify a document is returned as-is when no migrations are registered."""
        doc = {"schema_version": 1, "data": "test"}
        result = apply_migrations(doc)
        assert result == doc

    def test_applies_single_migration(self) -> None:
        """Verify a single migration is applied correctly."""

        @register_migration(2)
        def migrate_v2(doc: dict) -> dict:
            doc["category_breakdown"] = []
            doc["schema_version"] = 2
            return doc

        doc = {"schema_version": 1, "user_id": "u1"}
        result = apply_migrations(doc, target_version=_TARGET_VERSION)
        assert result["schema_version"] == 2
        assert result["category_breakdown"] == []

    def test_applies_multiple_migrations_in_order(self) -> None:
        """Verify migrations are applied in version order."""

        @register_migration(3)
        def migrate_v3(doc: dict) -> dict:
            doc["field_v3"] = True
            doc["schema_version"] = 3
            return doc

        @register_migration(2)
        def migrate_v2(doc: dict) -> dict:
            doc["field_v2"] = True
            doc["schema_version"] = 2
            return doc

        doc = {"schema_version": 1}
        result = apply_migrations(doc, target_version=_TARGET_VERSION)
        assert result["schema_version"] == 3
        assert result["field_v2"] is True
        assert result["field_v3"] is True

    def test_skips_already_applied_migrations(self) -> None:
        """Verify migrations already applied (version <= doc version) are skipped."""

        @register_migration(2)
        def migrate_v2(doc: dict) -> dict:
            doc["migrated_v2"] = True
            doc["schema_version"] = 2
            return doc

        @register_migration(3)
        def migrate_v3(doc: dict) -> dict:
            doc["migrated_v3"] = True
            doc["schema_version"] = 3
            return doc

        # Doc is already at v2 — only v3 should be applied
        doc = {"schema_version": 2}
        result = apply_migrations(doc, target_version=_TARGET_VERSION)
        assert "migrated_v2" not in result
        assert result["migrated_v3"] is True
        assert result["schema_version"] == 3

    def test_stops_on_migration_failure(self) -> None:
        """Verify apply_migrations stops when a migration raises an exception."""

        @register_migration(2)
        def migrate_v2(doc: dict) -> dict:
            raise RuntimeError("migration failed")

        @register_migration(3)
        def migrate_v3(doc: dict) -> dict:
            doc["migrated_v3"] = True
            doc["schema_version"] = 3
            return doc

        doc = {"schema_version": 1}
        result = apply_migrations(doc, target_version=_TARGET_VERSION)
        # v2 failed, so v3 should not be applied
        assert "migrated_v3" not in result
        assert result["schema_version"] == 1

    def test_uses_target_version_parameter(self) -> None:
        """Verify the target_version parameter limits which migrations are applied."""

        @register_migration(2)
        def migrate_v2(doc: dict) -> dict:
            doc["migrated_v2"] = True
            doc["schema_version"] = 2
            return doc

        @register_migration(3)
        def migrate_v3(doc: dict) -> dict:
            doc["migrated_v3"] = True
            doc["schema_version"] = 3
            return doc

        doc = {"schema_version": 1}
        result = apply_migrations(doc, target_version=2)
        assert result["migrated_v2"] is True
        assert "migrated_v3" not in result
        assert result["schema_version"] == 2

    def test_doc_without_schema_version_defaults_to_1(self) -> None:
        """Verify documents without schema_version default to version 1."""

        @register_migration(2)
        def migrate_v2(doc: dict) -> dict:
            doc["migrated"] = True
            doc["schema_version"] = 2
            return doc

        doc = {"data": "no version field"}
        result = apply_migrations(doc, target_version=_TARGET_VERSION)
        assert result["migrated"] is True
        assert result["schema_version"] == 2

    def test_doc_at_target_version_is_unchanged(self) -> None:
        """Verify a doc already at the target schema version is returned as-is."""

        @register_migration(2)
        def migrate_v2(doc: dict) -> dict:
            doc["changed"] = True
            doc["schema_version"] = 2
            return doc

        doc = {"schema_version": 2}
        result = apply_migrations(doc, target_version=2)
        assert "changed" not in result


class TestGetMigrationStatus:
    """Tests for the get_migration_status function."""

    def setup_method(self) -> None:
        """Clear the migration registry before each test."""
        _MIGRATIONS.clear()

    def test_returns_current_schema_version(self) -> None:
        """Verify status includes the current schema version."""
        status = get_migration_status()
        assert status["current_schema_version"] == _CURRENT_SCHEMA_VERSION

    def test_returns_empty_migrations_when_none_registered(self) -> None:
        """Verify status shows empty list when no migrations are registered."""
        status = get_migration_status()
        assert status["registered_migrations"] == []
        assert status["migration_count"] == 0

    def test_returns_registered_migrations(self) -> None:
        """Verify status includes registered migration versions."""

        @register_migration(2)
        def m2(doc: dict) -> dict:
            return doc

        @register_migration(5)
        def m5(doc: dict) -> dict:
            return doc

        status = get_migration_status()
        assert status["registered_migrations"] == [2, 5]
        assert status["migration_count"] == 2

    def test_registered_migrations_are_sorted(self) -> None:
        """Verify migration versions are returned in sorted order."""

        @register_migration(5)
        def m5(doc: dict) -> dict:
            return doc

        @register_migration(2)
        def m2(doc: dict) -> dict:
            return doc

        @register_migration(3)
        def m3(doc: dict) -> dict:
            return doc

        status = get_migration_status()
        assert status["registered_migrations"] == [2, 3, 5]

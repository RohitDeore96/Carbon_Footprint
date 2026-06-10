"""Firestore schema migration and evolution strategy.

Firestore is schemaless, which eliminates traditional migration concerns
such as adding columns or changing data types at the database level.
However, existing documents may not include new fields, which can cause
runtime errors if the application expects them to exist.

This module provides a lightweight migration framework for handling
schema evolution in existing Firestore documents. Migrations are
registered as functions and can be applied on-demand or scheduled
via the admin endpoint.

Migration Strategy:
    1. **Additive Changes**: New fields should have sensible defaults
       in the application layer. The code should use ``dict.get(key, default)``
       to handle missing fields gracefully.

    2. **Breaking Changes**: When field types or semantics change, register
       a migration function that transforms existing documents to the new
       schema. Migrations should be idempotent and safe to run multiple times.

    3. **Deprecation**: Old fields should be kept for at least one release
       cycle before removal, with the application reading from the new field
       first and falling back to the old field.

    4. **Version Tracking**: Each document includes a ``schema_version`` field.
       Migrations check this field and only apply if the document version
       is below the target version.

Example Migration Registration:

    @register_migration(2)
    def migrate_v1_to_v2(doc: dict) -> dict:
        '''Add category_breakdown field to carbon_logs.'''
        if 'category_breakdown' not in doc:
            doc['category_breakdown'] = []
        doc['schema_version'] = 2
        return doc
"""

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Registry of migration functions keyed by target schema version
_MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}
_CURRENT_SCHEMA_VERSION: int = 1


def register_migration(
    version: int,
) -> Callable:
    """Decorator that registers a migration function for a schema version.

    Args:
        version: The target schema version this migration produces.

    Returns:
        A decorator that registers the function.
    """

    def decorator(
        func: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> Callable[[dict[str, Any]], dict[str, Any]]:
        _MIGRATIONS[version] = func
        return func

    return decorator


def apply_migrations(
    doc: dict[str, Any],
    target_version: int = _CURRENT_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Apply all pending migrations to a Firestore document.

    Migrations are applied in version order, starting from the document's
    current ``schema_version`` (defaulting to 1 if absent) up to the
    target version.

    Args:
        doc: A Firestore document dictionary.
        target_version: The desired schema version.

    Returns:
        The migrated document dictionary.
    """
    current_version = doc.get("schema_version", 1)
    for version in sorted(_MIGRATIONS.keys()):
        if current_version < version <= target_version:
            try:
                doc = _MIGRATIONS[version](doc)
                logger.info(
                    "Applied migration v%d to document (previous v%d)",
                    version,
                    current_version,
                )
                current_version = version
            except Exception as exc:
                logger.error(
                    "Migration v%d failed for document: %s",
                    version,
                    exc,
                )
                break
    return doc


def get_migration_status() -> dict[str, Any]:
    """Return the current migration registry status.

    Returns:
        A dictionary with current schema version and registered migrations.
    """
    return {
        "current_schema_version": _CURRENT_SCHEMA_VERSION,
        "registered_migrations": sorted(_MIGRATIONS.keys()),
        "migration_count": len(_MIGRATIONS),
    }

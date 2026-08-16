"""Database configuration helpers for Navistoat."""

import os

DEFAULT_DATABASE_URI = "sqlite://database.sqlite3"
ENV_DATABASE_URI = os.environ.get("MIRURAIN_DATABASE_URI", None)


def build_tortoise_config(uri: str) -> dict:  # pyright: ignore[reportMissingTypeArgument]
    """Build a Tortoise ORM configuration for the provided connection URI.

    Args:
        uri: Connection URI for the default database.

    Returns:
        Tortoise ORM configuration dictionary.
    """
    return {
        "connections": {"default": uri},
        "apps": {
            "models": {
                "models": ["navistoat.tables"],
                "default_connection": "default",
                "migrations": "navistoat.migrations",
            }
        },
    }


TORTOISE_ORM = build_tortoise_config(
    DEFAULT_DATABASE_URI if ENV_DATABASE_URI is None else ENV_DATABASE_URI
)

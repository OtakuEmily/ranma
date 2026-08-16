"""Application configuration handling."""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Stoat(BaseModel):
    """Configuration for interacting with Stoat.chat.

    Attributes:
        api_key: Stoat API key.
        is_bot: Whether the account is a bot. Defaults to True.
    """

    api_key: str
    is_bot: bool = True

class Server(BaseModel):
    """Configuration for interacting with the OpenSubsonic server.

    Attributes:
        api_key: The API key to authenticate with.
    """

    base_url: str
    api_key: str

class Database(BaseModel):
    """Database connection settings for Navistoat.

    Attributes:
        uri: Connection URI for any Tortoise ORM-compatible SQL backend.
    """

    uri: str


class Settings(BaseSettings):
    """Top-level runtime configuration for Navistoat.

    Attributes:
        stoat: Stoat configuration settings.
        database: Database configuration settings.
        server: OpenSubsonic server connection configuration.
    """

    stoat: Stoat
    database: Database
    server: Server

    model_config = SettingsConfigDict(
        env_prefix="navistoat_",
        env_nested_delimiter="_",
        env_nested_max_split=1,
    )


@lru_cache
def _get_settings() -> Settings:
    """Load environment variables and build a cached settings instance.

    Returns:
        Settings: Cached settings instance.
    """
    load_dotenv()
    return Settings()  # pyright: ignore[reportCallIssue]


settings = _get_settings()

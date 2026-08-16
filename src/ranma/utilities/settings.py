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
        username: The username to authenticate against. Cannot be combined with API_KEY.
        password: The password to authenticate with.
    """

    base_url: str

    # Mutually exclusive, API_KEY can NOT exist when USERNAME and PASSWORD are present, vice versa.
    api_key: str | None = None
    username: str | None = None
    password: str | None = None


class Settings(BaseSettings):
    """Top-level runtime configuration for Ranma.

    Attributes:
        stoat: Stoat configuration settings.
        database: Database configuration settings.
        server: OpenSubsonic server connection configuration.
    """

    stoat: Stoat
    server: Server

    model_config = SettingsConfigDict(
        env_prefix="ranma_",
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
    _settings = Settings()  # pyright: ignore[reportCallIssue]

    if (_settings.server.api_key is not None) and (_settings.server.username is not None):
        raise RuntimeError("API_KEY and USERNAME are set!")

    return _settings


settings = _get_settings()

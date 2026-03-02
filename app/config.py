from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str | None = None
    openai_model: str = "gpt-5"
    host: str = "127.0.0.1"
    port: int = 8443
    ssl_certfile: str = "certs/server.crt"
    ssl_keyfile: str = "certs/server.key"
    basic_auth_enabled: bool = True
    basic_auth_users_file: str = "config/basic_auth_users.json"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", case_sensitive=False)

    def resolve_path(self, value: str) -> Path:
        return Path(value).expanduser().resolve()


settings = Settings()

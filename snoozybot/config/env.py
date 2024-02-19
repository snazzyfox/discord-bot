from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvironmentConfig(BaseSettings):
    database_url: SecretStr = Field(...)
    short_logs: bool = Field(False)
    log_level: str | int = Field("INFO")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


envConfig = EnvironmentConfig()

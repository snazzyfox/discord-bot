from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvironmentConfig(BaseSettings):
    database_url: SecretStr = Field(..., env="database_url")
    short_logs: bool = Field(False, env="short_logs")
    log_level: str | int = Field("INFO", env="log_level")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


envConfig = EnvironmentConfig()

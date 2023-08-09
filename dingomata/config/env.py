from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvironmentConfig(BaseSettings):
    database_url: SecretStr = Field(..., env="database_url")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


envConfig = EnvironmentConfig()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Defaults target local development;
    production must override both via the environment.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://payflow:payflow@localhost:5432/payflow"
    payflow_webhook_secret: str = "whsec_test_123"

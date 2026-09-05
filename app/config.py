"""Configuracao da aplicacao, carregada de variaveis de ambiente / arquivo .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    secret_key: str = "dev-secret-key-troque-em-producao"

    admin_user: str = "comercial@amglogistica.com.br"
    admin_pass: str = "amg123"

    resend_api_key: str = ""
    email_from: str = "AMG Logistica <onboarding@resend.dev>"
    email_comercial: str = "comercial@amglogistica.com.br"

    base_url: str = "http://localhost:8000"
    database_url: str = "sqlite:///./amg.db"
    env: str = "dev"

    @property
    def is_dev(self) -> bool:
        return self.env.lower() != "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

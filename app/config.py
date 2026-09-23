"""Configuracao da aplicacao, carregada de variaveis de ambiente / arquivo .env."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    secret_key: str = "dev-secret-key-troque-em-producao"

    admin_user: str = "comercial@amglogistica.com.br"
    admin_pass: str = "amg123"

    resend_api_key: str = ""
    email_from: str = "AMG Logística <onboarding@resend.dev>"
    email_comercial: str = "comercial@amglogistica.com.br"
    # Destinatario do aviso interno de "OC enviada a Logistica", com o
    # responsavel comercial em copia.
    email_logistica: str = "josemarteixeiracosta@gmail.com"
    email_logistica_cc: str = "comercial4@amglog.com.br"
    # Enquanto nenhum dominio proprio estiver verificado no Resend, a conta
    # so consegue ENTREGAR e-mail pro proprio dono da conta -- qualquer
    # outro destinatario (cliente real, logistica, etc.) e rejeitado pela
    # API. Se preenchido, TODO e-mail (para + cc) e redirecionado pra esse
    # endereco, com o destinatario real anotado no assunto, em vez de
    # falhar silenciosamente. Remover essa variavel assim que um dominio
    # for verificado (ai os e-mails voltam a ir pro destinatario de verdade).
    email_destino: str = ""

    base_url: str = "http://localhost:8000"
    database_url: str = "sqlite:///./amg.db"
    env: str = "dev"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        # Render (e outros PaaS) fornecem "postgres://", mas o SQLAlchemy 2.x
        # exige o esquema "postgresql://" para o dialeto psycopg2.
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        return v

    @property
    def is_dev(self) -> bool:
        return self.env.lower() != "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

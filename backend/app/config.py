"""
Configuración de la aplicación.
Carga variables de entorno desde .env
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuración de la aplicación."""

    # Jira
    jira_url: str = "https://hosting-jira.1and1.org"
    jira_user: Optional[str] = None
    jira_password: Optional[str] = None

    # API
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:3008", "http://localhost:5178"]

    # Database
    database_path: str = "data/correlator.db"

    # Session
    session_secret: str = "change-me-in-production-use-a-real-secret-key"
    session_expire_hours: int = 24

    # Scoring defaults
    default_weight_time: float = 0.35
    default_weight_service: float = 0.30
    default_weight_infra: float = 0.20
    default_weight_org: float = 0.15

    # Ranking defaults
    default_top_results: int = 20

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Obtiene la configuración (cached)."""
    return Settings()

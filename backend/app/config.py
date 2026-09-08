"""Configuration settings loaded from environment variables."""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings. All values come from .env or environment variables."""

    # API Keys
    gemini_api_key: str = ""
    groq_api_key: str = ""

    # Database
    database_path: str = "./data/knowledge.db"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # LLM provider config
    llm_primary: str = "gemini"
    llm_fallback: str = "groq"

    # Page images directory
    pages_dir: str = "./data/pages"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton
settings = Settings()

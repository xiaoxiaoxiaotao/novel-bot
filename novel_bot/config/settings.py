from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_BASE_URL: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4o"
    
    workspace_path: str = "workspace"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

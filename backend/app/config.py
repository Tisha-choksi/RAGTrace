from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Audit Trail Middleware"
    database_url: str = "sqlite:///./data/audit_trail.db"
    chroma_dir: str = "./data/chroma"
    upload_dir: str = "./data/uploads"
    embedding_model: str = "all-MiniLM-L6-v2"
    ai_provider: str = "local"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_upload_mb: int = 50
    chroma_server_host: str = ""
    chroma_server_port: int = 8001

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def ensure_dirs(self) -> None:
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)
        Path(self.chroma_dir).mkdir(parents=True, exist_ok=True)
        Path("data").mkdir(parents=True, exist_ok=True)


settings = Settings()


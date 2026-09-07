from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql://myuser:123@localhost:5432/wpr"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384
    top_k: int = 5
    wikipedia_user_agent: str = "Wikipedia-Knowledge-Assistant/0.1"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

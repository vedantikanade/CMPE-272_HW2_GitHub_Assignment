# Authored by Vedanti Kanade
# Written by: [Your Name] - SJSU CMPE-272
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GITHUB_TOKEN: str
    GITHUB_OWNER: str
    GITHUB_REPO: str
    WEBHOOK_SECRET: str
    PORT: int = 8000

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Walk up from this file to find the .env at any level of the project tree
_here = Path(__file__).resolve()
_env_candidates = [
    str(_here.parents[0] / ".env"),   # app/core/.env
    str(_here.parents[1] / ".env"),   # app/.env
    str(_here.parents[2] / ".env"),   # backend/.env
    str(_here.parents[3] / ".env"),   # project root .env  ← this is where the keys live
    str(_here.parents[4] / ".env"),   # one more level up just in case
]


class Settings(BaseSettings):
    gemini_api_key: str = ""
    elastic_key: str = ""
    elastic_url: str = ""
    elastic_cluster: str = ""

    model_config = SettingsConfigDict(
        env_file=_env_candidates,
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

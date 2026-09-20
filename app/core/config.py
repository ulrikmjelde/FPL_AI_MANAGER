from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

fpl_refresh_token_file: str | None = None

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    app_env: str = 'dev'
    log_level: str = 'INFO'
    database_url: str = 'postgresql+asyncpg://fpl:fpl@db:5432/fpl'
    poll_seconds: int = 90
    process_initial_history: bool = False

    openai_api_key: str
    openai_model: str = 'gpt-5.6-terra'

    x_bearer_token: str
    x_creator_username: str

    fpl_entry_id: int
    fpl_access_token: str
    fpl_refresh_token: str | None = None
    fpl_oidc_client_id: str = 'bfcbaf69-aade-4c1b-8f00-c1cb8a193030'
    fpl_oidc_token_url: str = 'https://account.premierleague.com/as/token'

    auto_transfer: bool = False
    allow_alternative_players: bool = True
    allow_multi_transfer: bool = True
    allow_points_hits: bool = False
    max_points_hit: int = 0
    max_transfers_per_decision: int = 3
    min_source_confidence: float = 0.95
    min_ai_confidence: float = 0.85
    auto_use_chips: bool = False

    youtube_transcripts: bool = True
    notify_webhook_url: str | None = None

    @field_validator('database_url')
    @classmethod
    def asyncpg_url(cls, value: str) -> str:
        if value.startswith('postgresql://'):
            return value.replace('postgresql://', 'postgresql+asyncpg://', 1)
        return value


@lru_cache

def get_settings() -> Settings:
    return Settings()

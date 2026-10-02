from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    database_url: str = "sqlite:///./ministry_dashboard.db"
    # Comma-separated extra CORS origins (e.g. your deployed Vercel URL) on top of
    # the local-dev defaults baked into app.main - set on the backend host, not here.
    cors_origins: str = ""

    # A copy-pasted env var on a host dashboard (Render, etc.) very easily picks up a
    # trailing newline or leading/trailing space - that turns a visibly-correct-looking
    # API key into one the Anthropic API rejects as invalid, with no indication why.
    # Stripping here means that class of bug just can't happen.
    @field_validator("anthropic_api_key", "database_url", "cors_origins", mode="after")
    @classmethod
    def _strip_whitespace(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    database_url: str = "sqlite:///./ministry_dashboard.db"
    # Comma-separated extra CORS origins (e.g. your deployed Vercel URL) on top of
    # the local-dev defaults baked into app.main - set on the backend host, not here.
    cors_origins: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

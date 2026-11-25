from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    env: str = "development"
    database_url: str = ""
    api_hmac_secret: str = ""
    gemini_api_key: str = ""
    gemini_model: str = ""
    ai_enabled: str = "false"  # a string so anything other than exactly "true" keeps AI off
    ai_timeout_s: float = 6
    cron_secret: str = ""
    session_daily_ai: int = 20
    ip_daily_ai: int = 40
    global_daily_ai: int = 200

    @property
    def ai_ready(self) -> bool:
        return self.ai_enabled == "true" and bool(self.gemini_api_key.strip()) and bool(self.gemini_model.strip())
